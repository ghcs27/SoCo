
"""This module is for parsing functions, which require the available classes
and upgrade functions to be registered in the `_DIDL_CLASS_TO_CLASS` dict and
`_UPGRADE_FUNCTIONS` list

"""

from __future__ import absolute_import

import sys
import logging

from .xml import (
    XML, ns_tag
)
from .exceptions import DIDLMetadataError


_LOG = logging.getLogger(__name__)
if not (sys.version_info[0] == 2 or sys.version_info[1] == 6):
    _LOG.addHandler(logging.NullHandler())
_LOG.debug('%s imported', __name__)

_DIDL_CLASS_TO_CLASS = {}
_UPGRADE_FUNCTIONS = []


def from_didl_string(string):
    """Convert a unicode xml string to a list of `DIDLObjects <DidlObject>`.

    Args:
        string (str): A unicode string containing an XML representation of one
            or more DIDL-Lite items (in the form  ``'<DIDL-Lite ...>
            ...</DIDL-Lite>'``)

    Returns:
        list: A list of one or more instances of `DidlObject` or a subclass
    """
    items = []
    root = XML.fromstring(string.encode('utf-8'))
    for elt in root:
        if elt.tag.endswith('item') or elt.tag.endswith('container'):
            item_class = elt.findtext(ns_tag('upnp', 'class'))

            # In case this class has an # specified unofficial
            # subclass, ignore it by stripping it from item_class
            if '.#' in item_class:
                item_class = item_class[:item_class.find('.#')]

            # Try to resolve item_class via the _DIDL_CLASS_TO_CLASS dict
            try:
                cls = _DIDL_CLASS_TO_CLASS[item_class]
            except KeyError:
                raise DIDLMetadataError("Unknown UPnP class: %s" % item_class)
            item = cls.from_element(elt)

            # Try to upgrade the item with the functions in _UPGRADE_FUNCTIONS
            for upgrade in _UPGRADE_FUNCTIONS:
                item = upgrade(item)

            items.append(item)
        else:
            # <desc> elements are allowed as an immediate child of <DIDL-Lite>
            # according to the spec, but I have not seen one there in Sonos, so
            # we treat them as illegal. May need to fix this if this
            # causes problems.
            raise DIDLMetadataError("Illegal child of DIDL element: <%s>"
                                    % elt.tag)
    _LOG.error(
        'Created data structures: %.20s (CUT) from Didl string "%.20s" (CUT)',
        items, string,
    )
    return items
