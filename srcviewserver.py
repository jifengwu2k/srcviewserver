# Copyright (c) 2026 Jifeng Wu
# Licensed under the MIT License. See LICENSE file in the project root
# for full license information.
from __future__ import print_function, unicode_literals

import argparse
import codecs
import logging
import os
import posixpath
import socket
import time



from typing import (
    BinaryIO,
    Dict,
    List,
    Optional,
)


from fspathverbs import (
    Child,
    Current,
    FSPathVerb,
    Parent,
    Root,
    compile_to_fspathverbs,
)
from guess_file_mime_type import guess_file_mime_type
from httppackets.http_1_1_parser import (
    Decision,
    ParserError,
    parse_http_1_1_requests,
)
from httppackets.http_1_1_serializer import (
    SupportsRead,
    serialize_http_1_1_response,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_for_filename
from pygments.util import ClassNotFound
from six.moves.urllib.parse import quote, unquote, urlparse
from textcompat import filesystem_str_to_text


DEFAULT_BIND = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER = "sourceview"


ERROR_MESSAGES = {
    400: "Bad request",
    403: "Forbidden",
    404: "Not found",
    405: "Method not allowed",
    406: "Not acceptable",
    408: "Request timeout",
    414: "URI too long",
    500: "Internal server error",
    501: "Not implemented",
    503: "Service unavailable",
}  # type: Dict[int, str]


def format_current_date_time():
    # type: () -> str
    """Return the current time as an HTTP-date string."""
    return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(time.time()))


def write_error(stream, code):
    # type: (BinaryIO, int) -> None
    """Write an HTTP error response to *stream*."""
    message = ERROR_MESSAGES.get(code, "Unknown error")
    
    body = '\n'.join(
        (
            '<!DOCTYPE HTML>',
            '<html>',
            '<head>',
            '<meta charset="utf-8">',
            '<title>%d %s</title>' % (code, message),
            '</head>',
            '<body>',
            '<h1>%d %s</h1>' % (code, message),
            '</body>',
            '</html>',
        )
    )

    body_bytes = body.encode("utf-8")
    
    headers = {
        "content-type": ["text/html; charset=utf-8"],
        "content-length": [str(len(body_bytes))],
        "connection": ["close"],
        "date": [format_current_date_time()],
        "server": [SERVER],
    }  # type: Dict[str, List[str]]

    serialize_http_1_1_response(
        stream,
        status_code=code,
        reason=message,
        headers=headers,
        body=body_bytes,
    )


class FileBodyReader(SupportsRead):
    __slots__ = ("_file",)

    def __init__(self, file_obj):
        # type: (BinaryIO) -> None
        self._file = file_obj

    def read(self, n=-1):
        # type: (int) -> bytes
        return self._file.read(n)


def serve_path(wf, method, path, target):
    # type: (BinaryIO, str, str, str) -> None
    """Serve *path* as a response on *wf*."""
    if os.path.isdir(path):
        if method == "GET":
            # Directory listing
            names = os.listdir(path)
            names.sort()

            listing_html_lines = [
                '<!DOCTYPE HTML>',
                '<html>',
                '<head>',
                '<meta charset="utf-8">',
                '<title>Directory listing for %s</title>' % (target,),
                '</head>',
                '<body>',
                '<h1>Directory listing for %s</h1>' % (target,),
                '<hr/>',
                '<ul>',
            ]  # type: List[str]

            for name in names:
                quoted = quote(name)
                display = filesystem_str_to_text(name)
                full = os.path.join(path, name)

                if os.path.isdir(full):
                    listing_html_lines.append('<li><a href="%s/">%s/</a></li>' % (quoted, display))
                else:
                    listing_html_lines.append('<li><a href="%s">%s</a></li>' % (quoted, display))

            listing_html_lines += [
                '</ul>',
                '<hr/>',
                '</body>',
                '</html>'
            ]

            listing_html = '\n'.join(listing_html_lines)

            listing_html_bytes = listing_html.encode("utf-8")
                
            resp_headers = {
                "content-type": ["text/html; charset=utf-8"],
                "content-length": [str(len(listing_html_bytes))],
                "connection": ["close"],
                "date": [format_current_date_time()],
                "server": [SERVER],
            }  # type: Dict[str, List[str]]

            serialize_http_1_1_response(
                wf,
                status_code=200,
                reason="OK",
                headers=resp_headers,
                body=listing_html_bytes,
            )
        else:
            resp_headers = {
                "content-type": ["text/html; charset=utf-8"],
                "content-length": ["0"],
                "connection": ["close"],
                "date": [format_current_date_time()],
                "server": [SERVER],
            }  # type: Dict[str, List[str]]
            
            serialize_http_1_1_response(
                wf,
                status_code=200,
                reason="OK",
                headers=resp_headers,
                body=None,
            )
    else:
        # File
        content_type = guess_file_mime_type(path)
        if method == "GET":
            try:
                lexer = get_lexer_for_filename(path)
            except ClassNotFound:
                lexer = None

            if lexer is not None:
                with codecs.open(path, 'r', encoding='utf-8') as inf:
                    code = inf.read()
                
                formatter = HtmlFormatter(nowrap=True, noclasses=True, style='default')
                highlighted = highlight(code, lexer, formatter)

                input_file_name_with_ext = os.path.basename(path)

                html_content = '\n'.join(
                    (
                        '<!DOCTYPE html>',
                        '<html>',
                        '<head>',
                        '<meta charset="utf-8">',
                        '<title>%s</title>' % filesystem_str_to_text(input_file_name_with_ext),
                        '<style> .code { white-space: pre-wrap; word-break: break-word; font-family: monospace } </style>',
                        '</head>',
                        '<body>',
                        '<div class="code">',
                        highlighted,
                        '</div>',
                        '</body>',
                        '</html>',
                    )
                )

                body_bytes = html_content.encode("utf-8")

                resp_headers = {
                    "content-type": ["text/html; charset=utf-8"],
                    "content-length": [str(len(body_bytes))],
                    "connection": ["close"],
                    "date": [format_current_date_time()],
                    "server": [SERVER],
                }  # type: Dict[str, List[str]]

                serialize_http_1_1_response(
                    wf,
                    status_code=200,
                    reason="OK",
                    headers=resp_headers,
                    body=body_bytes,
                )
            else:
                with open(path, "rb") as inf:
                    resp_headers = {
                        "content-type": [content_type],
                        "connection": ["close"],
                        "date": [format_current_date_time()],
                        "server": [SERVER],
                    }  # type: Dict[str, List[str]]

                    serialize_http_1_1_response(
                        wf,
                        status_code=200,
                        reason="OK",
                        headers=resp_headers,
                        body=FileBodyReader(inf),
                    )
        else:
            file_size = os.path.getsize(path)

            resp_headers = {
                "content-type": [content_type],
                "content-length": [str(file_size)],
                "connection": ["close"],
                "date": [format_current_date_time()],
                "server": [SERVER],
            }  # type: Dict[str, List[str]]

            serialize_http_1_1_response(
                wf,
                status_code=200,
                reason="OK",
                headers=resp_headers,
                body=None,
            )


def handle_connection(sock):
    # type: (socket.socket) -> None
    """Handle a single TCP connection: parse request, serve response."""

    rf = sock.makefile("rb")
    wf = sock.makefile("wb")

    cwd = os.getcwd()

    def on_headers(method, target, headers):
        # type: (str, str, Dict[str, List[str]]) -> Decision
        if method not in ("GET", "HEAD"):
            write_error(wf, 501)
        else:
            parsed = urlparse(target)
            decoded = unquote(parsed.path)

            # Compile the URL path into verbs using POSIX semantics.
            url_verbs = compile_to_fspathverbs(decoded, posixpath.split)

            # Build a relative component list from the verbs.
            rel_components = []  # type: List[str]
            for verb in url_verbs:
                if isinstance(verb, Root):
                    rel_components = []
                elif isinstance(verb, Parent):
                    if rel_components:
                        rel_components.pop()
                elif isinstance(verb, Child):
                    rel_components.append(verb.child)
                # Current is a no-op

            # Join with cwd to get the filesystem path.
            if rel_components:
                path = os.path.join(cwd, *rel_components)
            else:
                path = cwd

            if not os.path.exists(path):
                write_error(wf, 404)
            else:
                serve_path(wf, method, path, target)
            
        return Decision.ABORT

    def on_body(reader):
        pass

    try:
        parse_http_1_1_requests(rf, on_headers=on_headers, on_body=on_body)
    except ParserError as e:
        write_error(wf, 400)
    except Exception as e:
        logging.exception(e)
        write_error(wf, 500)
    finally:
        rf.close()
        wf.close()
        sock.close()


def main():
    # type: () -> None
    """Entry point for ``python -m httpserver``."""
    parser = argparse.ArgumentParser(
        description="Simple HTTP server using httppackets (http.server lookalike).",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=DEFAULT_PORT,
        help="port to listen on",
    )
    parser.add_argument(
        "--bind",
        "-b",
        type=str,
        default=DEFAULT_BIND,
        help="address to bind to",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    bind = args.bind
    port = args.port

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((bind, port))
    sock.listen(128)

    logging.info(
        "Serving HTTP on http://%s:%d/ ...",
        bind,
        port,
    )

    try:
        while True:
            client_sock, client_addr = sock.accept()
            handle_connection(client_sock)
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received, shutting down.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
