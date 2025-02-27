signal-sticker-tool
===================

A tool to create and upload [Signal](https://signal.org) sticker packs from the command line.



## Introduction

`signal-sticker-tool` is a tool to generate Signal sticker packs from directories with images and a (possibly auto-generated) YAML definition and upload them to Signal servers. This approach is more practical than using then Signal desktop client, a slow and bloated Electron app, despite it still being necessary to get the authentication credentials. It can also work as a back-end for automatic sticker pack conversion scripts.

This is a command line tool; internally, the sticker packaging and upload work is done by the library [signalstickers-client](https://github.com/signalstickers/signalstickers-client).



## Installation

In any current Linux distribution, to install the current stable version in your `$HOME` directory, just type:

    pip3 install signal-sticker-tool

This assumes pip3 is installed and configured. You may also want to install in an isolated virtual environment with:

    python3 -m venv my-venv
    . my-venv/bin/activate
    pip install signal-sticker-tool

`signal-sticker-tool`'s target operating system is a POSIX-compatible system (aka. any modern Unix-like as Linux, several BSDs, and MacOS X). It may or may not work on Windows, I am just not interested in it, but I will accept Windows-related code contributions if somebody sends me them.


### Installing development versions

Development versions come fresh from the Git repository and may have bug fixes that were not released yet, improvements that are being worked on, and (possibly) new bugs. If you want to play with this version, it is recommended to install it in an isolated virtual environment with the following commands:

    python3 -m venv my-venv
    . my-venv/bin/activate
    pip install https://github.com/ittner/signal-sticker-tool/archive/master.zip

This does not requires Git to be installed in your machine. However, if you have it, you can replace the last command with a:

    pip install git+https://github.com/ittner/signal-sticker-tool/

or just clone the repository, create and enable the virtual-env, and run a `pip install .` from the working copy. Developers wanting to modify the code or contribute back some change will probably choose this way first.




## Creating a sticker pack

First, a primer: Signal stickers are stored in packs that are private and end-to-end encrypted, and neither the Signal CDN nor other users can read them, but servers can know the number of images in a pack, their approximate sizes, and who downloads them; by Signal standards, stickers are very leaky in the metadata department. They are saved **read-only** in the servers, indexed by a *pack_id* and encrypted with a *pack_key*. This key never leaves the clients by default and when sites like [signalstickers.com](https://signalstickers.com) publish a pack, they are just intentionally sharing both the id and the key with everybody. Once a pack is uploaded, it can not be modified anymore and will remain taking up space on the servers — so, remember this before doing any stupid test! These are the technicalities you need to know before making a sticker pack, but signalstickers-client has a [detailed explanation](https://github.com/signalstickers/signalstickers-client/blob/master/STICKERS_INTERNALS.md).


Start by creating a directory for the sticker pack. The name of this directory does not matter, just choose something meaningful for your pack. In this example we will call it `dinner-reactions`.

Then copy or move the image files there. Signal has a few [requirements and recommendations](https://support.signal.org/hc/en-us/articles/360031836512-Stickers#sticker_reqs) for making good stickers, and it is very important to follow them. There must be an image for every sticker and, optionally, one for the cover of this pack.

Add the sticker pack definition, a [YAML](https://en.wikipedia.org/wiki/YAML) file called `stickers.yaml` that must be saved in this same directory. The format is the following:

```yaml
meta:
  author: Samwise Gamgee
  cover: cover.webp
  title: Dinner reactions
stickers:
- chr: '😋'
  file: sticker_01.webp
- chr: '🥔'
  file: sticker_02.webp
- chr: '🍄'
  file: sticker_03.webp
```

Where:
- `meta` is a metadata header represented by a dictionary with two required entries (`title` for the pack title and `author` for the author's name) and one optional `cover` for the cover image file. If no cover is given, Signal will take the first sticker for it;
- `stickers` is a list of dictionaries, each one with a required `file` entry for the image file and an optional `chr` with the emoji associated with the sticker. While technically optional, emojis are strongly recommended as they allow Signal to suggest the sticker in the selection box. The stickers will be put in the pack in the order given by this list.

Any other top-level element present in this file will be ignored and preserved through updates, so it is safe to add them for e.g. extra data used by an automatic sticker conversion tool.

Creating a `stickers.yaml` manually for every pack may be a tedious process, but `signal-sticker-tool` can generate one automatically from the information that is already available. For that, after copying the images to the pack directory, just enter into it and run `signal-sticker-tool init`. Example:

    $ cd dinner-reactions
    $ signal-sticker-tool init --title "Dinner reactions" --author "Samwise Gamgee"

The results will be the following:

- The command will recognize all image types relevant for stickers (WebP, JPEG, PNG, GIF ...);
- If a file named `cover.*` is found, it will be used as the cover for the pack;
- All other image files will be added to the sticker list in strict alphabetical order. It is possible, of course, to reorder them by editing the YAML file afterwards: renaming files before init or reordering elements afterwards is just a matter of preference;
- Arguments `--title` (short form: `-T`) and `--author` (short form: `-A`) are optional. If not given, placeholder values will be used;
- No sticker/emoji association will be created by default and you will need to edit the file afterwards to add it. However, if option `--read-emojis` (short form: `-E`) is given, command will read emojis from standard input, one per line, and assign them to the image files in alphabetical order. Just double-check the results before uploading the pack;
- By default, command `init` will refuse to run if a `stickers.yaml` is already present in the directory. It is possible to override this with argument `--update` (short form: `-u`) and then `init` will update the file with the new information while preserving the existing one (this includes emoji assignments, but **not** the file ordering).

As a practical matter, it is recommended to adopt the convention of naming the cover file as `cover.webp` (or other image format) and the sticker files as something else in alphabetical order (e.g. `sticker_01.webp`, `sticker_02.webp`, `sticker_03.webp`, ...). This will spare a lot of time by allowing `signal-sticker-tool init` to do the most tedious part of the work for you.

Once the YAML definition is completed, you can generate a preview of the entire pack with:

    $ signal-sticker-tool preview

This command will create a HTML file called "preview.html" in the pack directory with all stickers and the associated emoji in the same order they will appear in the selection window. Open this file in your browser, double-check it, and then upload the pack to Signal.



### Uploading sticker packs to Signal

Signal requires users to be authenticated before they can upload sticker packs (but they also say they do not keep association between stickers and who uploaded them). For now, the only way to log-in is "borrowing" credentials from an already logged Signal Desktop client. To do this, launch the client from the command line with option passing the option `--enable-dev-tools`, open the Developer Tools and type `window.reduxStore.getState().items.uuid_id` to get the user name and `window.reduxStore.getState().items.password` to get the password. Then type

    $ signal-sticker-tool login

and enter the user name and password. They will be saved in your home directory and reused until you log-out with command `signal-sticker-tool logout`. This whole process is a bit convoluted and I hope that I can change it in the future.

Once you are logged in, enter the sticker directory and type

    $ signal-sticker-tool upload

And everything is done! Once the stickers finish uploading, URLs with the pack will be shown:

    This pack is available in URL:
      https://signal.art/addstickers/#pack_id=XXXXXXXXXXXXXXXXXXX&pack_key=XXXXXXXXXXXXXXXXXXX

    And to open it directly in the Android or iOS app:
      sgnl://addstickers/?pack_id=XXXXXXXXXXXXXXXXXXX&pack_key=XXXXXXXXXXXXXXXXXXX


    Signal stickers are encrypted and private. Nobody will be able to use or
    even see anything about them without this id and key. If you want to keep
    this pack for yourself, send this URL to your phone to add it; i you want
    to share it publicly, send this URL to https://signalstickers.com/ (but
    once published, there is no way to make it private again).

`signal-sticker-tool` will also save the pack_id and the pack_key to a file `uploaded.yaml` in the target directory and refuse to upload the same set again if this file already exists, showing the values from the previous upload instead. Since stickers can not be deleted or edited, this is a way to prevent accidental reuploads that only take unnecessary space on Signal servers. If you changed something and need to upload the pack again, just delete or rename the file to something else.

Once a pack is uploaded, you can also use command `signal-sticker-tool url` to print the URL used to import the sticker pack into Signal. This command shows **only** the URL, so it is useful for piping the results to another command. It also makes very simple to show the URL as a QR code: just install a pure-Python generator with `pip install qrcode` and then use it to print the code in the terminal with:

    signal-sticker-tool url | qr




### Downloading existing sticker packs

It is possible to download an existing Signal sticker pack as a sticker directory, complete with an automatically generated `stickers.yaml` for easy editing, using the command `signal-sticker-tool download PACK-URL` (or optionally `signal-sticker-tool -p DEST-PATH download PACK-URL` to save directly into a new directory), where `PACK-URL` is the signal.art URL used for adding the sticker to Signal. Example:

    $ signal-sticker-tool -p bandit-the-cat download "https://signal.art/addstickers/#pack_id=9acc9e8aba563d26a4994e69263e3b25&pack_key=5a6dff3948c28efb9b7aaf93ecc375c69fc316e78077ed26867a14d10a0f6a12"

The command also allows downloading packs using the pack id and key directly, as follows:

    $ signal-sticker-tool -p bandit-the-cat download 9acc9e8aba563d26a4994e69263e3b25 5a6dff3948c28efb9b7aaf93ecc375c69fc316e78077ed26867a14d10a0f6a12

Downloaded image files will be named sequentially (`sticker_00.webp`, `sticker_01.webp`, `sticker_02.webp`, ...) so if you, for example, want to add a new sticker after `sticker_01.webp`, just name it `sticker_01a.webp` (keeping the alphabetical order), run `signal-sticker-tool init -u` in that directory, edit `stickers.yaml` to set the new emoji and re-upload.



## Contributing

`signal-sticker-tool` is [hosted in GitHub](https://github.com/ittner/signal-sticker-tool/) and contributions of any kind are welcome (code, bug reports, etc.). If you don't have a GitHub account, you can also clone the repo, host your changes somewhere else and [contact me](#contact-information) instead.

If you change the code, please run in through pyflakes for static analysis and [black](https://pypi.org/project/black/) to ensure a consistent formatting.




## License

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.




## Contact information

- Author: Alexandre Erwin Ittner
- Email: alexandre@ittner.com.br
- Web: https://www.ittner.com.br
- PGP/GnuPG key: [0x48CF13A4BE42B8BD](https://www.ittner.com.br/key.pub.asc)

