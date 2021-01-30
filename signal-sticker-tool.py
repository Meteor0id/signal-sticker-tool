#!/usr/bin/env python3

#
# signal-sticker-tool - Create Signal sticker packs from YAML definitions
# Copyright (C) 2021  Alexandre Erwin Ittner <alexandre@ittner.com.br>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#


import argparse
import yaml
import os
import sys
import getpass
import asyncio
from signalstickers_client import StickersClient
from signalstickers_client.models import LocalStickerPack, Sticker

try:
    import xdg.BaseDirectory

    _creds_file_base = os.path.abspath(xdg.BaseDirectory.xdg_config_home)
except ModuleNotFoundError:
    _creds_file_base = os.path.expanduser("~/.config")

# Default file name for user credentials.
DEFAULT_CREDS_FILE = os.path.abspath(
    os.path.join(_creds_file_base, "signal-sticker-tool", "credentials.yaml")
)

# YAML file with the sticker pack definition.
SRC_YAML_FNAME = "stickers.yaml"

# YAML file with the results of the upload.
RES_YAML_FNAME = "uploaded.yaml"

# Suffixes for valid image types used in the "init" command. Always in lower case.
VALID_IMAGE_TYPES = set(["webp", "jpg", "jpeg", "gif", "png"])


class AbortException(Exception):
    pass


def read_sticker_emoji_list(path, read_emojis=False, cover_fname="cover"):

    files = os.listdir(path)
    image_files = [
        os.path.normpath(f)
        for f in files
        if f.split(".", 1)[-1].lower() in VALID_IMAGE_TYPES
    ]
    image_files.sort()

    # Find cover image (if any) and remove it from regular stickers.
    cover = None
    if cover_fname:
        tmplst = list()
        for tmp in image_files:
            if tmp.split(".", 1)[0] == cover_fname:
                if not cover:
                    # Things get funny when several files mathches the cover.
                    cover = tmp
            else:
                tmplst.append(tmp)
        image_files = tmplst

    if read_emojis:
        txt = sys.stdin.read()
        emojis = [e for e in txt.split() if e.strip() != ""]
    else:
        emojis = len(image_files) * [None]

    if len(emojis) != len(image_files):
        raise AbortException(
            "Can't generate the sequence automatically. The number of entries in "
            "the emoji sequence does not match the number of files in the source "
            "directory."
        )

    sticker_list = {image_files[i]: emojis[i] for i in range(len(image_files))}
    return sticker_list, cover


def create_pack_yaml(title, author, path=".", read_emojis=False, allow_update=False):
    """Make a skeleton stickers.yaml from files in the target directory and,
    optionally, a list of emojis read from stdin.
    """

    def_file_path = os.path.join(path, SRC_YAML_FNAME)
    if os.path.exists(def_file_path):
        # Hello race condition my old friend...
        if not allow_update:
            raise AbortException("File %s already exists." % def_file_path)
        with open(def_file_path) as fp:
            base = yaml.safe_load(fp)
    else:
        base = {}

    read_stickers, read_cover = read_sticker_emoji_list(path, read_emojis)

    # Try to reuse existing meta-information, if possible.
    meta = dict()
    if ("meta" in base) and (type(base["meta"]) == dict):
        meta = base["meta"]

    if "title" not in meta:
        meta["title"] = None
    meta["title"] = title or meta["title"] or "Put pack title here"

    if "author" not in meta:
        meta["author"] = None
    meta["author"] = author or meta["author"] or "Put author name here"

    cur_cover = meta["cover"] if "cover" in meta else None
    meta["cover"] = read_cover or cur_cover

    base["meta"] = meta

    # Try to reuse existing file:emoji associations, if possible.
    cur_stickers = dict()
    if "stickers" in base and type(base["stickers"]) == list:
        lst = base["stickers"]
        for itm in lst:
            if type(itm) == dict and "chr" in itm and "file" in itm:
                cur_stickers[itm["file"]] = itm["chr"]

    sticker_list = list()
    for fname in read_stickers.keys():
        emoji = read_stickers[fname]
        if not emoji and fname in cur_stickers:
            emoji = cur_stickers[fname]
        if not emoji:
            emoji = ""
        sticker_list.append({"chr": emoji, "file": fname})

    base["stickers"] = sticker_list

    with open(def_file_path, "w") as fp:
        yaml.safe_dump(base, fp, allow_unicode=True, default_flow_style=False)


class StickerDefinitionError(AbortException):
    def __init__(self, desc):
        super().__init__("Error in the sticker definition file: " + desc)


def parse_pack_yaml(basepath):
    yfname = os.path.join(basepath, SRC_YAML_FNAME)
    ydata = yaml.safe_load(open(yfname))

    if not "meta" in ydata:
        raise StickerDefinitionError("sticker metadata not defined")

    meta = ydata["meta"]
    if type(meta) != dict:
        raise StickerDefinitionError('Element "meta" must be a map')
    if not "title" in meta or meta["title"].strip() == "":
        raise StickerDefinitionError("Pack title name not defined")
    if not "author" in meta or meta["author"].strip() == "":
        raise StickerDefinitionError("Author name not defined")
    if "cover" in meta and meta["cover"] != None and meta["cover"].strip() != "":
        meta["cover"] = os.path.abspath(os.path.join(basepath, meta["cover"]))
    else:
        meta["cover"] = None

    if not "stickers" in ydata:
        raise StickerDefinitionError("Sticker list not defined")
    stickers = ydata["stickers"]
    if type(stickers) != list:
        raise StickerDefinitionError('Element "stickers" must be a list')
    if len(stickers) == 0:
        raise StickerDefinitionError("No stickers defined")

    for st in stickers:
        if type(st) != dict:
            raise StickerDefinitionError("Unexpected entry type found in sticker list")
        if not "chr" in st:
            # No emoji attached to sticker. Is this even valid?!
            st["chr"] = ""
        if not "file" in st:
            raise StickerDefinitionError('Entry without required element "file"')
        fname = st["file"]
        fpath = os.path.join(basepath, fname)
        if not os.path.exists(fpath):
            raise StickerDefinitionError(
                'Bad file name for sticker, file "%s" not found.' % (fpath)
            )
        st["path"] = os.path.abspath(fpath)

    return ydata


def get_user_credentials(args):
    try:
        with open(args.cred_file) as fp:
            creds = yaml.safe_load(fp)
        if ("username" in creds) and ("password" in creds):
            return (creds["username"], creds["password"])
    except FileNotFoundError:
        raise AbortException('Credentials file not found. Try "login" first')


def do_login(args):
    sys.stdout.write(
        """
For now, the only way to login is "borrowing" the credentials from a
already logged-in Signal Desktop client. On your client, open the Developer
Tools and type "window.reduxStore.getState().items.uuid_id" to the the user
name and "window.reduxStore.getState().items.password" to get the password.

This is *really* *ugly* and will change in the future.

"""
    )

    sys.stdout.write("Username: ")
    sys.stdout.flush()
    username = sys.stdin.readline()
    username = username.strip()

    if username == "":
        print("Username is empty. Login aborted.")
        return
    password = getpass.getpass("Password: ")

    try:
        os.unlink(args.cred_file)
    except FileNotFoundError:
        pass

    creds = {"username": username, "password": password}
    cred_file = os.path.abspath(args.cred_file)
    os.makedirs(os.path.dirname(cred_file), mode=0o700, exist_ok=True)
    with open(os.open(cred_file, os.O_CREAT | os.O_WRONLY, 0o600), "w") as fp:
        yaml.safe_dump(creds, fp, allow_unicode=True, default_flow_style=False)

    print(
        'Credentials for user "%s" saved in "%s". Use "logout" to remove them.'
        % (username, cred_file)
    )


def do_logout(args):
    try:
        os.unlink(args.cred_file)
    except FileNotFoundError:
        pass
    print("You are logged out.")


def init_pack(args):
    create_pack_yaml(args.title, args.author, args.path, args.read_emojis, args.update)


def print_pack_information(info):
    if (not "id" in info) or (not "key" in info):
        raise ValueError("Pack info has no elements 'id' and 'key'")
    print(
        "This pack is available in URL:\n"
        "  https://signal.art/addstickers/#pack_id=%s&pack_key=%s"
        % (info["id"], info["key"])
    )
    print(
        "\nAnd to open it directly in the Android or iOS app:\n"
        "  sgnl://addstickers/?pack_id=%s&pack_key=%s" % (info["id"], info["key"])
    )
    print(
        "\n\nSignal stickers are encrypted and private. Nobody will be able "
        "to use or even see anything about them without this  id and key. "
        "If you want to keep this pack for yourself, send this URL to your "
        "phone to add them. If you want to share them publically, send this "
        "URL to https://signalstickers.com/ (but once published, there is no "
        "way to make them private again).\n"
    )


async def upload_pack(args):

    res_path = os.path.join(args.path, RES_YAML_FNAME)
    if os.path.exists(res_path):
        with open(res_path) as fp:
            info = yaml.safe_load(fp)
        print(
            'File "%s" found: this sticker set was already uploaded! If '
            "you changed something, delete or rename this file and upload "
            "it again.\n" % res_path
        )
        print_pack_information(info)
        return

    ydata = parse_pack_yaml(args.path)
    creds = get_user_credentials(args)

    pack = LocalStickerPack()
    pack.title = ydata["meta"]["title"]
    pack.author = ydata["meta"]["author"]

    for itm in ydata["stickers"]:
        st = Sticker()
        st.id = pack.nb_stickers
        st.emoji = itm["chr"]
        with open(itm["path"], "rb") as fp:
            st.image_data = fp.read()
        pack._addsticker(st)

    cover_path = ydata["meta"]["cover"]
    if cover_path:
        cover = Sticker()
        cover.id = pack.nb_stickers
        with open(cover_path, "rb") as fp:
            cover.image_data = fp.read()
        pack.cover = cover

    async with StickersClient(creds[0], creds[1]) as client:
        pack_id, pack_key = await client.upload_pack(pack)

    info = {"id": pack_id, "key": pack_key}
    with open(res_path, "w") as fp:
        yaml.safe_dump(info, fp, allow_unicode=True, default_flow_style=False)

    print_pack_information(info)


def run_upload_pack(args):
    # We can't take advantage of async code here :/
    # TODO: Well, at least we should handle timeouts.
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(upload_pack(args))


def main():
    main_parser = argparse.ArgumentParser(
        description="Create Signal sticker packs from YAML definitions",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    main_parser.add_argument(
        "-p",
        "--path",
        action="store",
        default=".",
        type=str,
        metavar="DIRECTORY",
        help="Path to the directory of the sticker pack.",
    )

    main_parser.add_argument(
        "-c",
        "--cred-file",
        action="store",
        default=DEFAULT_CREDS_FILE,
        type=str,
        metavar="PATH",
        help="Path to the user credentials file",
    )

    subparsers = main_parser.add_subparsers(dest="cmd")

    login_parser = subparsers.add_parser(
        "login",
        help=(
            "Ask for Signal credentials and save them in a credential file "
            "for future use. For now only a login and password, obtained "
            "from Signal Desktop client, is supported."
        ),
    )

    login_parser.set_defaults(func=do_login)

    logout_parser = subparsers.add_parser(
        "logout", help="Remove saved Signal credentials."
    )

    logout_parser.set_defaults(func=do_logout)

    init_parser = subparsers.add_parser(
        "init",
        help=(
            "Create a basic " + SRC_YAML_FNAME + " file in the pack directory "
            "to be edited by the user. The sticker list will include all "
            "image files with recognized extensions ("
            + ", ".join(sorted(list(VALID_IMAGE_TYPES)))
            + ")."
        ),
    )

    init_parser.set_defaults(func=init_pack)

    init_parser.add_argument(
        "-T",
        "--title",
        action="store",
        default=None,
        type=str,
        metavar="TITLE",
        help="Use this title for the pack",
    )

    init_parser.add_argument(
        "-A",
        "--author",
        action="store",
        default=None,
        type=str,
        metavar="NAME",
        help="Use this author for the pack",
    )

    init_parser.add_argument(
        "-E",
        "--read-emojis",
        action="store_true",
        default=False,
        help=(
            "Read the list of emojis from the standard input when "
            "initializing a sticker pack. There must be one emoji per line "
            "(ignoring empty lines). This script will assign the emojis in "
            "order they were read to the recognized image files the pack "
            "directory read in strict alphabetical order. The number of files "
            "and emojis MUST match, otherwise the an error will be emitted. "
            "Please check if the assignment is the intended one before "
            "uploading!"
        ),
    )

    init_parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        default=False,
        help=(
            "Allows the command to update a existing pack definition. If "
            "this option is not given, the command will not overwrite an "
            "existing pack definition file."
        ),
    )

    upload_parser = subparsers.add_parser(
        "upload", help="Upload the pack to Signal servers."
    )
    upload_parser.set_defaults(func=run_upload_pack)

    try:
        args = main_parser.parse_args()
        if not args.cmd:
            raise AbortException("No command given, try --help")
        args.func(args)

    except AbortException as exc:
        sys.stdout.write("Error: %s\n" % str(exc))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
