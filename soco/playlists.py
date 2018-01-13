# -*- coding: utf-8 -*-

"""Utilities for editing playlists.

The playlits referenced here are those under "Sonos Playlists" in the
official controller, not "Music Library" > "Imported Playlists".
"""

from .compat import UnicodeType
from . import discovery
from .data_structures import (
    DidlResource,
    DidlPlaylistContainer
)
from .data_structures import to_didl_string


class PlaylistManager(object):
    """Class for Sonos playlist management."""

    # pylint: disable=invalid-name, protected-access
    def __init__(self, soco=None):
        """
         Args:
             soco (`SoCo`, optional): A `SoCo` instance to query for music
                 library information. If `None`, or not supplied, a random
                 `SoCo` instance will be used.
        """
        self.soco = soco or discovery.any_soco()
        self.music_library = self.soco.music_library
        self.avTransport = self.soco.avTransport
        self.contentDirectory = self.soco.contentDirectory

    @staticmethod
    def _make_playlist_container(item_id, title):
        """Create a playlist container from id and title.

        Args:
            item_id (str): The playlist item id.
            title (str): The playlist title.

        Returns:
            An instance of
            :py:class:`~.soco.data_structures.DidlPlaylistContainer`
        """
        obj_id = item_id.split(':', 2)[1]
        uri = "file:///jffs/settings/savedqueues.rsq#{0}".format(obj_id)

        res = [DidlResource(uri=uri, protocol_info="x-rincon-playlist:*:*:*")]
        return DidlPlaylistContainer(resources=res, title=title,
            parent_id='SQ:', item_id=item_id)

    def create_sonos_playlist(self, title):
        """Create a new empty Sonos playlist.

        Args:
            title (str): Name of the playlist

        Returns:
            An instance of
            :py:class:`~.soco.data_structures.DidlPlaylistContainer`
        """
        response = self.avTransport.CreateSavedQueue([
            ('InstanceID', 0),
            ('Title', title),
            ('EnqueuedURI', ''),
            ('EnqueuedURIMetaData', ''),
        ])

        item_id = response['AssignedObjectID']
        return self._make_playlist_container(item_id, title)

    # pylint: disable=invalid-name
    def create_sonos_playlist_from_queue(self, title, player=None):
        """Create a new Sonos playlist from the current queue.

        Args:
            title (str): Name of the playlist
            player (SoCo, optional): The SoCo instance to save the queue from.
                If None is given, the instance associated to this object is
                used.

        Returns:
            An instance of
            :py:class:`~.soco.data_structures.DidlPlaylistContainer`
        """
        # Note: probably same as Queue service method SaveAsSonosPlaylist
        # but this has not been tested.  This method is what the
        # controller uses.
        player = player or self.soco
        response = player.avTransport.SaveQueue([
            ('InstanceID', 0),
            ('Title', title),
            ('ObjectID', '')
        ])

        item_id = response['AssignedObjectID']
        return self._make_playlist_container(item_id, title)

    def remove_sonos_playlist(self, sonos_playlist):
        """Remove a Sonos playlist.

        Args:
            sonos_playlist (`DidlPlaylistContainer`): Sonos playlist to remove
                or the item_id (str).

        Returns:
            bool: True if succesful, False otherwise

        Raises:
            SoCoUPnPException: If sonos_playlist does not point to a valid
                object.

        """
        object_id = getattr(sonos_playlist, 'item_id', sonos_playlist)
        return self.contentDirectory.DestroyObject([('ObjectID', object_id)])

    def add_item_to_sonos_playlist(self, queueable_item, sonos_playlist):
        """Adds a queueable item to a Sonos' playlist.

        Args:
            queueable_item (`DidlItem`): the item to add to the Sonos' playlist
            sonos_playlist (`DidlPlaylistContainer`): the Sonos' playlist to
                which the item should be added
        """
        # Get the update_id for the playlist
        response, _ = self.music_library._music_lib_search(
            sonos_playlist.item_id, 0, 1)
        update_id = response['UpdateID']

        # Form the metadata for queueable_item
        metadata = to_didl_string(queueable_item)

        # Make the request
        self.avTransport.AddURIToSavedQueue([
            ('InstanceID', 0),
            ('UpdateID', update_id),
            ('ObjectID', sonos_playlist.item_id),
            ('EnqueuedURI', queueable_item.resources[0].uri),
            ('EnqueuedURIMetaData', metadata),
            # 2 ** 32 - 1 = 4294967295, this field has always this value. Most
            # likely, playlist positions are represented as a 32 bit uint and
            # this is therefore the largest index possible. Asking to add at
            # this index therefore probably amounts to adding it "at the end"
            ('AddAtIndex', 4294967295)
        ])

    def reorder_sonos_playlist(self, sonos_playlist, tracks, new_pos,
                               update_id=0):
        """Reorder and/or Remove tracks in a Sonos playlist.

        The underlying call is quite complex as it can both move a track
        within the list or delete a track from the playlist.  All of this
        depends on what tracks and new_pos specify.

        If a list is specified for tracks, then a list must be used for
        new_pos. Each list element is a discrete modification and the next
        list operation must anticipate the new state of the playlist.

        If a comma formatted string to tracks is specified, then use
        a similiar string to specify new_pos. Those operations should be
        ordered from the end of the list to the beginning

        See the helper methods
        :py:meth:`clear_sonos_playlist`, :py:meth:`move_in_sonos_playlist`,
        :py:meth:`remove_from_sonos_playlist` for simplified usage.

        update_id - If you have a series of operations, tracking the update_id
        and setting it, will save a lookup operation.

        Examples:
          To reorder the first two tracks::

            # sonos_playlist specified by the DidlPlaylistContainer object
            sonos_playlist = device.get_sonos_playlists()[0]
            device.reorder_sonos_playlist(sonos_playlist,
                                          tracks=[0, ], new_pos=[1, ])
            # OR specified by the item_id
            device.reorder_sonos_playlist('SQ:0', tracks=[0, ], new_pos=[1, ])

          To delete the second track::

            # tracks/new_pos are a list of int
            device.reorder_sonos_playlist(sonos_playlist,
                                          tracks=[1, ], new_pos=[None, ])
            # OR tracks/new_pos are a list of int-like
            device.reorder_sonos_playlist(sonos_playlist,
                                          tracks=['1', ], new_pos=['', ])
            # OR tracks/new_pos are strings - no transform is done
            device.reorder_sonos_playlist(sonos_playlist, tracks='1',
                                          new_pos='')

          To reverse the order of a playlist with 4 items::

            device.reorder_sonos_playlist(sonos_playlist, tracks='3,2,1,0',
                                          new_pos='0,1,2,3')

        Args:
            sonos_playlist
                (:py:class:`~.soco.data_structures.DidlPlaylistContainer`): The
                Sonos playlist object or the item_id (str) of the Sonos
                playlist.
            tracks: (list): list of track indices(int) to reorder. May also be
                a list of int like things. i.e. ``['0', '1',]`` OR it may be a
                str of comma separated int like things. ``"0,1"``.  Tracks are
                **0**-based. Meaning the first track is track 0, just like
                indexing into a Python list.
            new_pos (list): list of new positions (int|None)
                corresponding to track_list. MUST be the same type as
                ``tracks``. **0**-based, see tracks above. ``None`` is the
                indicator to remove the track. If using a list of strings,
                then a remove is indicated by an empty string.
            update_id (int): operation id (default: 0) If set to 0, a lookup
                is done to find the correct value.

        Returns:
            dict: Which contains 3 elements: change, length and update_id.
                Change in size between original playlist and the resulting
                playlist, the length of resulting playlist, and the new
                update_id.

        Raises:
            SoCoUPnPException: If playlist does not exist or if your tracks
                and/or new_pos arguments are invalid.
        """
        # allow either a string 'SQ:10' or an object with item_id attribute.
        object_id = getattr(sonos_playlist, 'item_id', sonos_playlist)

        if isinstance(tracks, UnicodeType):
            track_list = [tracks, ]
            position_list = [new_pos, ]
        elif isinstance(tracks, int):
            track_list = [tracks, ]
            if new_pos is None:
                new_pos = ''
            position_list = [new_pos, ]
        else:
            track_list = [str(x) for x in tracks]
            position_list = [str(x) if x is not None else '' for x in new_pos]
        # track_list = ','.join(track_list)
        # position_list = ','.join(position_list)
        if update_id == 0:  # retrieve the update id for the object
            response, _ = self.music_library._music_lib_search(object_id, 0, 1)
            update_id = response['UpdateID']
        change = 0

        for track, position in zip(track_list, position_list):
            if track == position:   # there is no move, a no-op
                continue
            response = self.avTransport.ReorderTracksInSavedQueue([
                ("InstanceID", 0),
                ("ObjectID", object_id),
                ("UpdateID", update_id),
                ("TrackList", track),
                ("NewPositionList", position),
            ])
            change += int(response['QueueLengthChange'])
            update_id = int(response['NewUpdateID'])
        length = int(response['NewQueueLength'])
        response = {'change': change,
                    'update_id': update_id,
                    'length': length}
        return response

    def clear_sonos_playlist(self, sonos_playlist, update_id=0):
        """Clear all tracks from a Sonos playlist.
        This is a convenience method for :py:meth:`reorder_sonos_playlist`.

        Example::

            device.clear_sonos_playlist(sonos_playlist)

        Args:
            sonos_playlist
                (:py:class:`~.soco.data_structures.DidlPlaylistContainer`):
                Sonos playlist object or the item_id (str) of the Sonos
                playlist.
            update_id (int): Optional update counter for the object. If left
                at the default of 0, it will be looked up.

        Returns:
            dict: See :py:meth:`reorder_sonos_playlist`

        Raises:
            ValueError: If sonos_playlist specified by string and is not found.
            SoCoUPnPException: See :py:meth:`reorder_sonos_playlist`
        """
        if not isinstance(sonos_playlist, DidlPlaylistContainer):
            sonos_playlist = self.get_sonos_playlist_by_attr('item_id',
                                                             sonos_playlist)
        count = self.music_library.browse(ml_item=sonos_playlist).total_matches
        tracks = ','.join([str(x) for x in range(count)])
        if tracks:
            return self.reorder_sonos_playlist(sonos_playlist, tracks=tracks,
                                               new_pos='', update_id=update_id)
        else:
            return {'change': 0, 'update_id': update_id, 'length': count}

    def move_in_sonos_playlist(self, sonos_playlist, track, new_pos,
                               update_id=0):
        """Move a track to a new position within a Sonos Playlist.
        This is a convenience method for :py:meth:`reorder_sonos_playlist`.

        Example::

            device.move_in_sonos_playlist(sonos_playlist, track=0, new_pos=1)

        Args:
            sonos_playlist
                (:py:class:`~.soco.data_structures.DidlPlaylistContainer`):
                Sonos playlist object or the item_id (str) of the Sonos
                playlist.
            track (int): **0**-based position of the track to move. The first
                track is track 0, just like indexing into a Python list.
            new_pos (int): **0**-based location to move the track.
            update_id (int): Optional update counter for the object. If left
                at the default of 0, it will be looked up.

        Returns:
            dict: See :py:meth:`reorder_sonos_playlist`

        Raises:
            SoCoUPnPException: See :py:meth:`reorder_sonos_playlist`
        """
        return self.reorder_sonos_playlist(sonos_playlist, int(track),
                                           int(new_pos), update_id)

    def remove_from_sonos_playlist(self, sonos_playlist, track, update_id=0):
        """Remove a track from a Sonos Playlist.
        This is a convenience method for :py:meth:`reorder_sonos_playlist`.

        Example::

            device.remove_from_sonos_playlist(sonos_playlist, track=0)

        Args:
            sonos_playlist
                (:py:class:`~.soco.data_structures.DidlPlaylistContainer`):
                Sonos playlist object or the item_id (str) of the Sonos
                playlist.
            track (int): *0**-based position of the track to move. The first
                track is track 0, just like indexing into a Python list.
            update_id (int): Optional update counter for the object. If left
                at the default of 0, it will be looked up.

        Returns:
            dict: See :py:meth:`reorder_sonos_playlist`

        Raises:
            SoCoUPnPException: See :py:meth:`reorder_sonos_playlist`
        """
        return self.reorder_sonos_playlist(sonos_playlist, int(track), None,
                                           update_id)

    def get_sonos_playlists(self, *args, **kwargs):
        """Convenience method for `music_library.get_music_library_information`
        with ``search_type='sonos_playlists'``. For details of other arguments,
        see `that method
        <#soco.music_library.MusicLibrary.get_music_library_information>`_.
        """
        return self.music_library.get_sonos_playlists(*args, **kwargs)

    def get_sonos_playlist_by_attr(self, attr_name, match):
        """Return the first Sonos Playlist DidlPlaylistContainer that
        matches the attribute specified.

        Args:
            attr_name (str): DidlPlaylistContainer attribute to compare. The
                most useful being: 'title' and 'item_id'.
            match (str): Value to match.

        Returns:
            (:class:`~.soco.data_structures.DidlPlaylistContainer`): The
                first matching playlist object.

        Raises:
            (AttributeError): If indicated attribute name does not exist.
            (ValueError): If a match can not be found.

        Example::

            device.get_sonos_playlist_by_attr('title', 'Foo')
            device.get_sonos_playlist_by_attr('item_id', 'SQ:3')

        """
        for sonos_playlist in self.get_sonos_playlists():
            if getattr(sonos_playlist, attr_name) == match:
                return sonos_playlist
        raise ValueError('No match on "{0}" for value "{1}"'.format(attr_name,
                                                                    match))