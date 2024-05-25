################################################################################
# Tripcode function:
# References: https://blog.utgw.net/entry/2021/01/05/195013
#             http://en.wikipedia.org/wiki/Tripcode
#             https://py4chan.sourceforge.net/
#             https://pypi.org/project/tripcode/
# License: BSDLv2
# Language: Python 3
# OS: independence

__version__ = '0.1.4'


def tripcode(tripkey: str, encoding: str = None, errors: str = None) -> str:
    # xmlcharrefreplace, strict, ignore, replace, backslashreplace, surrogateescape, surrogatepass

    from passlib.hash import des_crypt
    from re import sub

    try:
        # treat as Shift-JIS bytes
        tripkey = bytes(tripkey, encoding='shift-jis', errors='strict')
        tripkey.decode('utf-8')
    except (UnicodeDecodeError,):
        # asian langs
        pass
    except (UnicodeEncodeError,):
        # european langs
        try:
            tripkey = bytes(tripkey, encoding='utf-8', errors='strict')
        except (UnicodeEncodeError,):
            # not latin alphabet
            tripkey = bytes(tripkey, encoding='utf-8', errors='xmlcharrefreplace')
    else:
        # ¯\_(ツ)_/¯
        pass
    # print(tripkey)

    salt = (tripkey + b'H.')[1:3]
    salt = sub(rb'[^\.-z]', b'.', salt)
    salt = salt.translate(bytes.maketrans(b':;<=>?@[\\]^_`', b'ABCDEFGabcdef'))

    # trip = des_crypt.hash(tripkey, salt=salt.decode('shift-jis'))
    trip = des_crypt.hash(tripkey, salt=salt.decode('utf-8'))
    trip = trip[-10:]

    return trip