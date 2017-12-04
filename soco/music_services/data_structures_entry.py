# -*- coding: utf-8 -*-

"""This module is for music service parsing and conversion functions that need
both music_services.data_structures and music_services.music_service.

"""

import sys
import logging
# pylint: disable=protected-access
from ..data_structures_entry import _UPGRADE_FUNCTIONS
from .data_structures import get_class
from .music_service import desc_from_uri
from ..compat import urlparse


_LOG = logging.getLogger(__name__)
if not (sys.version_info[0] == 2 and sys.version_info[1] == 6):
    _LOG.addHandler(logging.NullHandler())


# Obviously imcomplete, but missing entries will not result in error, but just
# a logged warning and no upgrade of the data structure
DIDL_NAME_TO_QUALIFIED_MS_NAME = {
    'DidlMusicTrack': 'MediaMetadataTrack'
}


def attempt_datastructure_upgrade(didl_item):
    """Attempt to upgrade a didl_item to a music services data structure
    if it originates from a music services

    """
    try:
        resource = didl_item.resources[0]
    except IndexError:
        _LOG.debug('Upgrade not possible, no resources')
        return didl_item

    if resource.uri.startswith('x-sonos-http'):
        # Get data
        uri = resource.uri
        # Now we need to create a DIDL item id. It seems to be based on the uri
        path = urlparse(uri).path
        # Strip any extensions, eg .mp3, from the end of the path
        path = path.rsplit('.', 1)[0]
        # The ID has an 8 (hex) digit prefix. But it doesn't seem to
        # matter what it is!
        item_id = '11111111{0}'.format(path)

        # Ignore other metadata for now, in future ask ms data
        # structure to upgrade metadata from the service
        metadata = {}
        try:
            metadata['title'] = didl_item.title
        except AttributeError:
            pass

        # Get class
        try:
            cls = get_class(DIDL_NAME_TO_QUALIFIED_MS_NAME[
                didl_item.__class__.__name__
            ])
        except KeyError:
            # The data structure should be upgraded, but there is an entry
            # missing from DIDL_NAME_TO_QUALIFIED_MS_NAME. Log this as a
            # warning.
            _LOG.warning(
                'DATA STRUCTURE UPGRADE FAIL. Unable to upgrade music library '
                'data structure to music service data structure because an '
                'entry is missing for %s in DIDL_NAME_TO_QUALIFIED_MS_NAME. '
                'This should be reported as a bug.',
                didl_item.__class__.__name__,
            )
            return didl_item

        upgraded_item = cls(
            item_id=item_id,
            desc=desc_from_uri(resource.uri),
            resources=didl_item.resources,
            uri=uri,
            metadata_dict=metadata,
        )
        _LOG.debug("Item %s upgraded to %s", didl_item, upgraded_item)
        return upgraded_item

    _LOG.debug('Upgrade not necessary')
    return didl_item

# add attempt_datastructure_upgrade to _UPGRADE_FUNCTIONS from
# data_structures_entry
_UPGRADE_FUNCTIONS.append(attempt_datastructure_upgrade)
