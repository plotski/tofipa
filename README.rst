``tofipa`` stands for \ **to**\ rrent \ **fi**\ les \ **pa**\ th. It finds the
files from a torrent beneath one or more download directories and prints the
first provided download directory where a file was found.

Existing files with the expected size and content but with a different path are
linked to the paths that are specified in the torrent.

A default download directory is used if not even a single file from the torrent
can be found in the file system.

The only output is the download directory. To actually add the torrent to your
client with the correct path, you are supposed to to wrap ``tofipa`` in a shell
script like this:

.. code-block:: bash

    #!/bin/bash
    set -o nounset  # Exit when unset variable is used
    set -o errexit  # Exit if any command fails

    torrent_file="$1"
    if [ -z "$torrent_file" ]; then
        echo "Usage $0 TORRENT" >&2
        exit 1
    fi

    # List of directories to your torrent downloads
    download_directories=(
        "$HOME"/downloads/
        '/media/My Archive/'
        /torrenteering/*
    )

    # The "${NAME[@]}" syntax quotes/escapes array items if necessary
    download_directory="$(tofipa --debug-file /tmp/tofipa.log "$torrent_file" "${download_directories[@]}")"

    # Failsafe to catch bugs
    if [ -z "$download_directory" ]; then
        echo "Download directory is empty! Bug or configuration mistake?" >&2
        exit 1
    else
        # Download $torrent_file with your client to $download_directory
        echo "Downloading $(basename "$torrent_file") to $download_directory"

        ### QbitTorrent
        HOST='http://localhost:8080'
        USERNAME='admin'
        PASSWORD='adminadmin'
        cookie=$(curl --silent --fail --show-error \
                      --header "Referer: $HOST" \
                      --cookie-jar - \
                      --data "username=$USERNAME&password=$PASSWORD" \
                      --request POST "$HOST/api/v2/auth/login")
        echo "$cookie" | curl --silent --fail --show-error \
                              --cookie - \
                              --form "filename=@$torrent_file" \
                              --form "savepath=$download_directory" \
                              --form "skip_checking=true" \
                              --request POST "$HOST/api/v2/torrents/add"

        ### Deluge
        HOST='localhost'
        PORT='58846'
        USERNAME='foo'
        PASSWORD='hunter2'
        deluge-console --daemon "$HOST" --port "$PORT" \
                       --username "$USERNAME" --password "$PASSWORD" \
                       "add \"$torrent_file\" --path \"$download_directory\""
        # TODO: Add --seed-mode to deluge-console.

        ### Transmission
        HOST='localhost:9091'
        USERNAME='foo'
        PASSWORD='hunter2'
        transmission-remote \
             "$HOST" --auth="$USERNAME:$PASSWORD" \
             --add "$torrent_file" \
             --download-dir "$download_directory"

        ### Rtorrent
        # I dunno. Figure it out and make a PR! :)
    fi

Details
-------

``TORRENT`` refers to the provided torrent file. ``LOCATION`` is a download
directory, i.e. the download path without the torrent's name.

1. Find files from ``TORRENT`` in the file system.

   a) For each file, find a file beneach each ``LOCATION`` with the same size as
      the one specified in ``TORRENT``.

   b) If there are multiple size matches, pick the file with the most similar
      name to the one specified in ``TORRENT``.

   c) Hash some pieces to confirm the file content is what ``TORRENT`` expects.

   d) Pick the first ``LOCATION`` where a matching file was found. This is the
      download directory that should be used when adding ``TORRENT`` to a
      BitTorrent client.

2. Make sure every matching file exists beneath the download directory with
   the same relative path as in ``TORRENT``. Try to create a hard link and
   default to a symbolic link if this fails because the link source and
   target are on different file systems.

3. Print the download directory where one or more files from ``TORRENT`` exists
   now.

   If no matching file is found, print the default location (``--default``) or
   the first ``LOCATION`` if there is no ``--default`` provided.

   This is the only output.
