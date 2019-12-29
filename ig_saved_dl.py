import json
import codecs
import datetime
import os.path
import logging
import argparse
import hashlib
from requests import get
try:
    from instagram_private_api import (
        Client, ClientError, ClientLoginError,
        ClientCookieExpiredError, ClientLoginRequiredError,
        __version__ as client_version)
except ImportError:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from instagram_private_api import (
        Client, ClientError, ClientLoginError,
        ClientCookieExpiredError, ClientLoginRequiredError,
        __version__ as client_version)

def to_json(python_object):
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')

def from_json(json_object):
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object

def onlogin_callback(api, new_settings_file):
    cache_settings = api.settings
    with open(new_settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('SAVED: {0!s}'.format(new_settings_file))

def save_img_url(img_url, target_dir):
    file_name = img_url[img_url.rfind("/")+1:]
    my_hash = hashlib.sha1(file_name.encode("UTF-8"))
    with open(target_dir+"/"+str(my_hash.hexdigest())+".jpg", "wb") as file:
        response = get(img_url)
        file.write(response.content)


if __name__ == '__main__':

    logging.basicConfig()
    LOGGER = logging.getLogger('instagram_private_api')
    LOGGER.setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description='IG saved collection downloader')
    parser.add_argument('-target-dir', '--target-dir', dest='target_dir', type=str, required=True)
    parser.add_argument('-settings', '--settings', dest='settings_file_path', type=str, required=True)
    parser.add_argument('-u', '--username', dest='username', type=str, required=True)
    parser.add_argument('-p', '--password', dest='password', type=str, required=True)
    parser.add_argument('-debug', '--debug', action='store_true')

    args = parser.parse_args()
    if args.debug:
        LOGGER.setLevel(logging.DEBUG)

    print('Client version: {0!s}'.format(client_version))
    device_id = None
    try:
        settings_file = args.settings_file_path
        if not os.path.isfile(settings_file):
            # settings file does not exist
            print('Unable to find file: {0!s}'.format(settings_file))

            # login new
            API = Client(
                args.username, args.password,
                on_login=lambda x: onlogin_callback(x, args.settings_file_path))
        else:
            with open(settings_file) as file_data:
                cached_settings = json.load(file_data, object_hook=from_json)
            print('Reusing settings: {0!s}'.format(settings_file))

            device_id = cached_settings.get('device_id')
            # reuse auth settings
            API = Client(
                args.username, args.password,
                settings=cached_settings)

    except (ClientCookieExpiredError, ClientLoginRequiredError) as exe:
        print('ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(exe))

        # Login expired
        # Do relogin but use default ua, keys and such
        API = Client(
            args.username, args.password,
            device_id=device_id,
            on_login=lambda x: onlogin_callback(x, args.settings_file_path))

    except ClientLoginError as exe:
        print('ClientLoginError {0!s}'.format(exe))
        sys.exit(9)
    except ClientError as exe:
        print('ClientError {0!s} (Code: {1:d}, Response: {2!s})'.format(exe.msg, exe.code, exe.error_response))
        sys.exit(9)
    except Exception as exe:
        print('Unexpected Exception: {0!s}'.format(exe))
        sys.exit(99)

    # show when login expires
    cookie_expiry = API.cookie_jar.auth_expires
    print('Cookie Expiry: {0!s}'.format(datetime.datetime.fromtimestamp(cookie_expiry).strftime('%Y-%m-%dT%H:%M:%SZ')))

    # populate media array
    saved_media = []
    feed_results = API.saved_feed()
    print("Saved items to download: " +str(len(feed_results['items'])))

    if len(feed_results['items']) > 0:
        saved_media.extend(feed_results.get('items', []))
        next_max_id = feed_results.get('next_max_id')

        while next_max_id:
            feed_results = API.saved_feed(max_id=next_max_id)
            saved_media.extend(feed_results.get('items', []))
            next_max_id = feed_results.get('next_max_id')

        # process saved_media
        for my_item in saved_media:
            # remove saved item
            status = API.unsave_photo(my_item['media']['id'])
            # if carousel_media - download each image
            if my_item['media']['media_type'] == 8:
                for caro_item in my_item['media']['carousel_media']:
                    if args.debug: print(my_item['media'])
                    save_img_url(caro_item['image_versions2']['candidates'][0]['url'], args.target_dir)
            if my_item['media']['media_type'] == 1:
                if args.debug: print(my_item['media'])
                save_img_url(my_item['media']['image_versions2']['candidates'][0]['url'], args.target_dir)
