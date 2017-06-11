# encoding: utf-8

from __future__ import unicode_literals

from collections import MutableMapping
from re import compile as r

from .compat import Path, str, py2, urlsplit, urljoin
from .part.auth import AuthenticationPart, SafeAuthenticationPart
from .part.authority import AuthorityPart, SafeAuthorityPart
from .part.base import BasePart
from .part.fragment import FragmentPart
from .part.heir import HeirarchicalPart
from .part.host import HostPart
from .part.password import PasswordPart
from .part.path import PathPart
from .part.port import PortPart
from .part.query import QueryPart
from .part.scheme import SchemePart
from .part.uri import URIPart
from .part.user import UserPart


class URI(MutableMapping):
	"""An object representing a URI (absolute or relative) and its components.
	
	Acts as a mutable mapping for manipulation of query string arguments. If the query string is not URL
	"form encoded" attempts at mapping access or manipulation will fail with a ValueError. No effort is made to
	preserve original query string key order. Repeated keys will have lists as values.
	"""
	
	# Skip allocation of a dictionary per instance by pre-defining available slots.
	__slots__ = ('_uri', '_scheme', '_user', '_password', '_host', '_port', '_path', '_query', '_fragment')
	
	__parts__ = ('scheme', 'authority', 'path', 'query', 'fragment')
	__safe_parts__ = ('scheme', 'safe_auth', 'host', 'port', 'path', 'query', 'fragment')
	
	# Scalar Parts
	scheme = SchemePart()
	user = UserPart()
	password = PasswordPart()
	host = HostPart()
	port = PortPart()
	path = PathPart()
	query = QueryPart()
	fragment = FragmentPart()
	
	# Compound Parts
	auth = authentication = AuthenticationPart()
	safe_auth = SafeAuthenticationPart()
	authority = AuthorityPart()
	safe_authority = SafeAuthorityPart()
	heirarchical = HeirarchicalPart()
	
	# Additional Compound Interfaces
	uri = URIPart(__parts__)  # Whole-URI retrieval or storage as string.
	safe_uri = URIPart(__safe_parts__, False)  # URI retrieval without password component, useful for logging.
	base = BasePart()
	summary = URIPart(('host', 'path'), False)
	
	# Common Aliases
	username = user
	hostname = host
	authentication = auth
	
	# Shortcuts
	
	@property
	def qs(self):
		query = self.query
		return str(query) if query else ""
	
	@qs.setter
	def qs(self, value):
		self.query = value
	
	# Python Object Protocol
	
	def __init__(self, _uri=None, **parts):
		"""Initialize a new URI from a passed in string and/or named parts.
		
		If both a base URI and parts are supplied than the parts will override those present in the URI.
		"""
		
		if hasattr(_uri, '__link__'):  # We utilize a custom object protocol to retrieve links to things.
			_uri = _uri.__link__
			
			# To allow for simpler cases, this attribute does not need to be callable.
			if callable(_uri): _uri = _uri()
		
		if hasattr(_uri, 'make_uri'):  # Support pathlib method protocol.
			_uri = _uri.make_uri()
		
		self.uri = _uri  # If None, this will also handle setting defaults.
		
		if parts:  # If not given a base URI, defines a new URI, otherwise update the given URI.
			allowable = set(self.__parts__ + self.__safe_parts__)
			for part, value in parts.items():
				if part not in allowable:
					raise TypeError("Unknown URI component: " + part)
				
				setattr(self, part, value)
	
	# Python Datatype Protocols
	
	def __repr__(self):
		"""Return a "safe" programmers' representation that omits passwords."""
		
		return "{0}('{1}')".format(self.__class__.__name__, self.safe_uri)
	
	def __str__(self):
		"""Return the Unicode text representation of this URI, including passwords."""
		
		return self.uri
	
	def __bytes__(self):
		"""Return the binary string representation of this URI, including passwords."""
		
		return self.uri.encode('utf-8')
	
	if py2:  # Adapt to Python 2 semantics on legacy versions.
		__unicode__ = __str__
		__str__ = __bytes__
	
	# Python Comparison Protocol
	
	def __eq__(self, other):
		"""Compare this URI against another value."""
		
		if not isinstance(other, self.__class__):
			other = self.__class__(other)
		
		# Because things like query string argument order may differ, but still be equivalent...
		for part in self.__parts__:
			if not getattr(self, part, None) == getattr(other, part, None):
				return False
		
		return True
	
	def __ne__(self, other):
		"""Inverse comparison support."""
		
		return not self == other
	
	def __bool__(self):
		"""Truthyness comparison."""
		
		return bool(self.url)
	
	if py2:
		__nonzero__ = __bool__
	
	# Python Mapping Protocol
	
	def __getitem__(self, name):
		"""Shortcut for retrieval of a query string argument."""
		
		if not isinstance(self._query, dict):
			raise ValueError("Query string is not manipulatable.")
		
		return self._query[name]
	
	def __setitem__(self, name, value):
		"""Shortcut for (re)assignment of query string arguments."""
		
		if not isinstance(self._query, dict):
			raise ValueError("Query string is not manipulatable.")
		
		self._uri = None  # Invalidate the cached string.
		self._query[name] = str(value)
	
	def __delitem__(self, name):
		"""Shortcut for removal of a query string argument."""
		
		if not isinstance(self._query, dict):
			raise ValueError("Query string is not manipulatable.")
		
		self._uri = None  # Invalidate the cached string.
		del self._query[name]
	
	def __iter__(self):
		"""Retrieve the query string argument names."""
		
		if not isinstance(self._query, dict):
			raise ValueError("Query string is not manipulatable.")
		
		return iter(self._query)
	
	def __len__(self):
		"""Determine the number of query string arguments."""
		
		if not isinstance(self._query, dict):
			return 0
		
		return len(self._query)
	
	# Path-like behaviours.
	
	def __div__(self, other):
		return URI(self, path=self.path / other, query='', fragment=None)
	
	__idiv__ = __div__
	__truediv__ = __div__
	
	def __floordiv__(self, other):
		other = str(other)
		
		if '://' in other:
			_, _, other = other.partition('://')
		
		return URI(str(self.scheme) + "://" + other)
	
	__ifloordiv__ = __floordiv__
	
	# Support Protocols
	
	__link__ = __str__  # Various
	make_uri = __str__  # Path
	
	def __html__(self):  # Markupsafe
		"""Return an HTML representation of this link.
		
		A link to http://example.com/foo/bar will result in:
		
			<a href="http://example.com/foo/bar">example.com/foo/bar</a>
		"""
		
		return '<a href="{address}">{summary}</a>'.format(
				address = escape(self.url),
				summary = escape(self.host + str(self.path)),
			)
	
	@property
	def relative(self):
		"""Identify if this URI is relative to some "current context".
		
		For example, if the protocol is missing, it's protocol-relative. If the host is missing, it's host-relative, etc.
		"""
		
		return not (self.scheme and self.host and self._path and self._path.is_absolute())
	
	def resolve(self, uri=None, **parts):
		"""Attempt to resolve a new URI given an updated URI, partial or complete."""
		
		if uri:
			result = URI(urljoin(str(self), str(uri)))
		else:
			result = URI(self)
		
		for part, value in parts.items():
			if part not in self.__parts__:
				raise TypeError("Unknown URI component: " + part)
			
			setattr(result, part, value)
		
		return result
