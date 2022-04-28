#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Exaplanation: Sumo Logic Backup! An easy way to get things backed up!

Usage:
   $ python  sumologic_backup  [ options ]

Style:
   Google Python Style Guide:
   http://google.github.io/styleguide/pyguide.html

    @name           sumologic_backup
    @version        2.00
    @author-name    Wayne Schmidt
    @author-email   wschmidt@sumologic.com
    @license-name   Apache 2.0
    @license-url    https://www.apache.org/licenses/LICENSE-2.0
"""

__version__ = 2.00
__author__ = "Wayne Schmidt (wschmidt@sumologic.com)"

### beginning ###
import json
import os
import sys
import time
import datetime
import argparse
import configparser
import http
import zipfile
import requests

sys.dont_write_bytecode = 1

MY_CFG = 'undefined'
PARSER = argparse.ArgumentParser(description="""

Allows you to backup content based on name, ID, or folder type

""")

PARSER.add_argument("-a", metavar='<secret>', dest='MY_SECRET', \
                    help="set api (format: <key>:<secret>) ")

PARSER.add_argument("-k", metavar='<client>', dest='MY_CLIENT', \
                    help="set key (format: <site>_<orgid>) ")

PARSER.add_argument("-c", metavar='<configfile>', dest='CONFIG', \
                    help="Specify config file")

PARSER.add_argument("-t", metavar='<target>', dest='BACKUPTARGET', \
                    default='Personal', help="Specify backup target (Personal or Global)")

PARSER.add_argument("-o", metavar='<outputdir>', dest='OUTPUTDIR', \
                    default='/var/tmp/sumologic-backup', help="Specify output dir")

PARSER.add_argument("-v", type=int, default=4, metavar='<verbose>', \
                    dest='verbose', help="increase verbosity")

PARSER.add_argument("-z", default=False, metavar='<zipfile>', \
                    dest='ZIPFILE', help="create zipfile (default: False)")

ARGS = PARSER.parse_args()

DELAY_TIME = .5

CONTENTMAP = dict()

REPORTTAG = 'sumologic-backup'

RIGHTNOW = datetime.datetime.now()

DATESTAMP = RIGHTNOW.strftime('%Y%m%d')

TIMESTAMP = RIGHTNOW.strftime('%H%M%S')

def resolve_option_variables():
    """
    Validates and confirms all necessary variables for the script
    """

    if ARGS.verbose > 6:
        print('Validating: {}'.format('supplied variables'))

    if ARGS.MY_SECRET:
        (keyname, keysecret) = ARGS.MY_SECRET.split(':')
        os.environ['SUMO_UID'] = keyname
        os.environ['SUMO_KEY'] = keysecret

    if ARGS.MY_CLIENT:
        (deployment, organizationid) = ARGS.MY_CLIENT.split('_')
        os.environ['SUMO_LOC'] = deployment
        os.environ['SUMO_ORG'] = organizationid

def resolve_config_variables():
    """
    Validates and confirms all necessary variables for the script
    """

    if ARGS.verbose > 6:
        print('Validating: {}'.format('configuration file variables'))

    if ARGS.CONFIG:
        cfgfile = os.path.abspath(ARGS.CONFIG)
        configobj = configparser.ConfigParser()
        configobj.optionxform = str
        configobj.read(cfgfile)

        if ARGS.verbose > 8:
            print(dict(configobj.items('Default')))

        if configobj.has_option("Default", "SUMO_TAG"):
            os.environ['SUMO_TAG'] = configobj.get("Default", "SUMO_TAG")

        if configobj.has_option("Default", "SUMO_UID"):
            os.environ['SUMO_UID'] = configobj.get("Default", "SUMO_UID")

        if configobj.has_option("Default", "SUMO_KEY"):
            os.environ['SUMO_KEY'] = configobj.get("Default", "SUMO_KEY")

        if configobj.has_option("Default", "SUMO_LOC"):
            os.environ['SUMO_LOC'] = configobj.get("Default", "SUMO_LOC")

        if configobj.has_option("Default", "SUMO_END"):
            os.environ['SUMO_END'] = configobj.get("Default", "SUMO_END")

        if configobj.has_option("Default", "SUMO_ORG"):
            os.environ['SUMO_ORG'] = configobj.get("Default", "SUMO_ORG")

def initialize_variables():
    """
    Validates and confirms all necessary variables for the script
    """

    resolve_option_variables()

    resolve_config_variables()

    try:
        my_uid = os.environ['SUMO_UID']
        my_key = os.environ['SUMO_KEY']

    except KeyError as myerror:
        print('Environment Variable Not Set :: {} '.format(myerror.args[0]))

    return my_uid, my_key

( sumo_uid, sumo_key ) = initialize_variables()

def create_backup_directory():
    """
    Create a backup directory for all of the content retrieved
    """

    time_tag = '.'.join((DATESTAMP, TIMESTAMP))
    backupdir = os.path.abspath(os.path.join(ARGS.OUTPUTDIR, time_tag, 'content'))
    os.makedirs(backupdir, exist_ok = True)

    reportdir = os.path.abspath(os.path.join(ARGS.OUTPUTDIR, time_tag, 'manifest'))
    os.makedirs(reportdir, exist_ok = True)

    return backupdir, reportdir

def build_details(source, parent_name, parent_oid_path, child):
    """
    Build the details for the client entry. If a folder recurse
    """

    my_type = child['itemType']
    uid_myself = child['id']
    uid_parent = child['parentId']

    my_name = child['name']

    my_path_list = ( parent_name, my_name )
    my_path_name = '/'.join(my_path_list)

    my_oid_list = ( parent_oid_path, uid_myself )
    my_oid_path = '/'.join(my_oid_list)

    if my_type == "Folder":
        content_list = source.get_myfolder(uid_myself)
        for content_child in content_list['children']:
            build_details(source, my_path_name, my_oid_path, content_child)

    CONTENTMAP[uid_myself] = dict()
    CONTENTMAP[uid_myself]["parent"] = uid_parent
    CONTENTMAP[uid_myself]["myself"] = uid_myself
    CONTENTMAP[uid_myself]["name"] = my_name
    CONTENTMAP[uid_myself]["path"] = my_path_name
    CONTENTMAP[uid_myself]["backupname"] = uid_myself
    CONTENTMAP[uid_myself]["backuppath"] = my_oid_path
    CONTENTMAP[uid_myself]["type"] = my_type

def create_manifest(manifestdir):
    """
    Now display the output we want from the CONTENTMAP data structure we made.
    """
    manifestname = '{}.csv'.format(REPORTTAG)
    manifestfile = os.path.join(manifestdir, manifestname)

    with open(manifestfile, 'a') as manifestobject:
        manifestobject.write('{},{},{},{},{},{},{}\n'.format("uid_myself", "uid_parent", \
                             "my_type", "my_name", "my_path", "backup_oid", "backup_path"))

        for content_item in CONTENTMAP:
            uid_parent = CONTENTMAP[content_item]["parent"]
            uid_myself = CONTENTMAP[content_item]["myself"]
            my_name = CONTENTMAP[content_item]["name"]
            my_path = CONTENTMAP[content_item]["path"]
            my_type = CONTENTMAP[content_item]["type"]
            my_backupname = CONTENTMAP[content_item]["backupname"]
            my_backuppath = CONTENTMAP[content_item]["backuppath"]

            manifestobject.write('{},{},{},\"{}\",\"{}\",{},{}\n'.format(uid_myself, uid_parent, \
                                 my_type, my_name, my_path, my_backupname, my_backuppath))

def create_personal_folder_content_map(source):
    """
    This builds the content map for the 'Personal' folder
    """

    content_list = source.get_myfolders()

    parent_name = "/" + content_list['name']
    parent_base_path = content_list['id']
    uid_myself = content_list['id']
    uid_parent = content_list['parentId']

    CONTENTMAP[uid_myself] = dict()
    CONTENTMAP[uid_myself]["parent"] = uid_parent
    CONTENTMAP[uid_myself]["myself"] = uid_myself
    CONTENTMAP[uid_myself]["name"] = parent_name
    CONTENTMAP[uid_myself]["path"] = "/" + parent_name
    CONTENTMAP[uid_myself]["backupname"] = parent_name
    CONTENTMAP[uid_myself]["backuppath"] = parent_base_path
    CONTENTMAP[uid_myself]["type"] = 'Folder'

    for child in content_list['children']:
        build_details(source, parent_name, parent_base_path, child)


def create_content_map(source):
    """
    This will collect the information on object for sumologic and then collect that into a list.
    the output of the action will provide a tuple of the orgid, objecttype, and id
    """

    if ARGS.BACKUPTARGET == 'Personal':

        create_personal_folder_content_map(source)

    else:

        gfolder_job = source.get_globalfolder_job()['id']
        gfolder_status = source.get_globalfolder_job_status(gfolder_job)['status']

        while gfolder_status != 'Success':
            gfolder_status = source.get_globalfolder_job_status(gfolder_job)['status']

        gfolder_result = source.get_globalfolder_job_result(gfolder_job)
        for child in gfolder_result['data']:
            print(child)
            if child['name'] == 'Personal':
                create_personal_folder_content_map(source)
            else:
                if child['itemType'] == 'Folder':
                    parent_name = ""
                    parent_base_path = child['id']
                    child_name = child['name']
                    uid_myself = child['id']
                    uid_parent = child['parentId']
                    build_details(source, parent_name, parent_base_path, child)
                else:
                    uid_myself = child['id']
                    uid_parent = child['parentId']
                    my_name = child['name']
                    my_type = child['itemType']

                    CONTENTMAP[uid_myself] = dict()
                    CONTENTMAP[uid_myself]["parent"] = uid_parent
                    CONTENTMAP[uid_myself]["myself"] = uid_myself
                    CONTENTMAP[uid_myself]["name"] = my_name
                    CONTENTMAP[uid_myself]["path"] = my_name
                    CONTENTMAP[uid_myself]["backupname"] = uid_myself
                    CONTENTMAP[uid_myself]["backuppath"] = uid_myself
                    CONTENTMAP[uid_myself]["type"] = my_type

    return CONTENTMAP

def create_backup_folders(backups):
    """
    This creates the intermediary directories so we can archive content an element at a time
    """

    for content_item in CONTENTMAP:
        backup_type = CONTENTMAP[content_item]["type"]
        backup_path = CONTENTMAP[content_item]["backuppath"]
        if backup_type == 'Folder':
            backup_target_dir = os.path.join(backups, backup_path)
            os.makedirs(backup_target_dir, exist_ok = True)

def backup_content(source,backupdir):
    """
    Runs through CONTENTMAP again this time exporting the content into an appropriate location
    """

    for content_item in CONTENTMAP:

        backup_type = CONTENTMAP[content_item]["type"]
        contentid = CONTENTMAP[content_item]["myself"]

        backuptarget = os.path.join(backupdir, CONTENTMAP[contentid]['backuppath']) + '.json'

        if backup_type != 'Folder':
            exportjob = source.start_export_job(contentid)['id']
            exportstatus = source.check_export_job_status(contentid,exportjob)['status']
            while exportstatus != 'Success':
                exportstatus = source.check_export_job_status(contentid,exportjob)['status']

            exportresult = source.check_export_job_result(contentid,exportjob)
        else:
            exportresult = source.get_myfolder(contentid)

        if ARGS.verbose > 4:
            print('Exporting: {} - {}'.format(contentid, backuptarget))

        ##### print(exportresult)
        ##### time.sleep(1)

        with open (backuptarget, "w") as backupobject:
            backupobject.write(json.dumps(exportresult) + '\n')

def create_zipfile(backupdir):
    """
    Create the zipfile from the backup directory
    """
    targetzipfile = '{}/{}.{}.{}.zip'.format(backupdir, REPORTTAG, DATESTAMP, TIMESTAMP )

    if ARGS.verbose > 4:
        print('Creating: zipfile {}'.format(targetzipfile))

    with zipfile.ZipFile(targetzipfile, 'w') as zipobject:
        for foldername, _subfolders, filenames in os.walk(backupdir):
            for filename in filenames:
                filepath = os.path.join(foldername, filename)
                zipobject.write(filepath, os.path.basename(filepath))

def main():
    """
    Setup the Sumo API connection, using the required tuple of region, id, and key.
    Once done, then run through the commands required
    """

    if ARGS.verbose > 3:
        print("Step-001: - Authenticating")

    source = SumoApiClient(sumo_uid, sumo_key)

    if ARGS.verbose > 3:
        print("Step-002: - Creating Supporting directories")

    (backups, reports ) = create_backup_directory()

    if ARGS.verbose > 3:
        print("Step-003: - Discovering content targets")

    _content_manifest = create_content_map(source)

    if ARGS.verbose > 3:
        print("Step-004: - Persisting content manifest")

    create_manifest(reports)

    if ARGS.verbose > 3:
        print("Step-005: - Create intermediate backup folders")

    create_backup_folders(backups)

    if ARGS.verbose > 3:
        print("Step-006: - Backing up content per manifest file")

    backup_content(source, backups)

    if ARGS.ZIPFILE is not False:
        create_zipfile(ARGS.OUTPUTDIR)

### class ###

class SumoApiClient():
    """
    This is defined SumoLogic API Client
    The class includes the HTTP methods, cmdlets, and init methods
    """

    def __init__(self, access_id, access_key, endpoint=None, cookieFile='cookies.txt'):
        """
        Initializes the Sumo Logic object
        """
        self.session = requests.Session()
        self.session.auth = (access_id, access_key)
        self.session.headers = {'content-type': 'application/json', \
            'accept': 'application/json'}
        cookiejar = http.cookiejar.FileCookieJar(cookieFile)
        self.session.cookies = cookiejar
        if endpoint is None:
            self.endpoint = self._get_endpoint()
        elif len(endpoint) < 3:
            self.endpoint = 'https://api.' + endpoint + '.sumologic.com/api'
        else:
            self.endpoint = endpoint
        if self.endpoint[-1:] == "/":
            raise Exception("Endpoint should not end with a slash character")

    def _get_endpoint(self):
        """
        SumoLogic REST API endpoint changes based on the geo location of the client.
        It contacts the default REST endpoint and resolves the 401 to get the right endpoint.
        """
        self.endpoint = 'https://api.sumologic.com/api'
        self.response = self.session.get('https://api.sumologic.com/api/v1/collectors')
        endpoint = self.response.url.replace('/v1/collectors', '')
        return endpoint

    def delete(self, method, params=None, headers=None, data=None):
        """
        Defines a Sumo Logic Delete operation
        """
        response = self.session.delete(self.endpoint + method, \
            params=params, headers=headers, data=data)
        if response.status_code != 200:
            response.reason = response.text
        response.raise_for_status()
        return response

    def get(self, method, params=None, headers=None):
        """
        Defines a Sumo Logic Get operation
        """
        response = self.session.get(self.endpoint + method, \
            params=params, headers=headers)
        if response.status_code != 200:
            response.reason = response.text
        response.raise_for_status()
        return response

    def post(self, method, data, headers=None, params=None):
        """
        Defines a Sumo Logic Post operation
        """
        response = self.session.post(self.endpoint + method, \
            data=json.dumps(data), headers=headers, params=params)
        if response.status_code != 200:
            response.reason = response.text
        response.raise_for_status()
        return response

    def put(self, method, data, headers=None, params=None):
        """
        Defines a Sumo Logic Put operation
        """
        response = self.session.put(self.endpoint + method, \
            data=json.dumps(data), headers=headers, params=params)
        if response.status_code != 200:
            response.reason = response.text
        response.raise_for_status()
        return response

### class ###

### methods ###

    def get_myfolders(self):
        """
        Using an HTTP client, this uses a GET to retrieve all information.
        """
        url = "/v2/content/folders/personal/"
        body = self.get(url).text
        results = json.loads(body)
        return results

    def get_myfolder(self, myself):
        """
        Using an HTTP client, this uses a GET to retrieve single information.
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/folders/" + str(myself)
        body = self.get(url).text
        results = json.loads(body)
        return results

    def get_globalfolder_job(self):
        """
        Using an HTTP client, this uses a GET to retrieve all information.
        """
        url = "/v2/content/folders/global"
        body = self.get(url).text
        results = json.loads(body)
        return results

    def get_globalfolder_job_status(self, myself):
        """
        Using an HTTP client, this uses a GET to retrieve single information.
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/folders/global/" + str(myself) + "/status"
        body = self.get(url).text
        results = json.loads(body)
        return results

    def get_globalfolder_job_result(self, myself):
        """
        Using an HTTP client, this uses a GET to retrieve single information.
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/folders/global/" + str(myself) + "/result"
        body = self.get(url).text
        results = json.loads(body)
        return results

    def start_export_job(self, myself):
        """
        Using an HTTP client, this starts an export job by passing in the content ID
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/" + str(myself) + "/export"
        body = self.post(url, data=str(myself)).text
        results = json.loads(body)
        return results

    def check_export_job_status(self, myself,jobid):
        """
        Using an HTTP client, this starts an export job by passing in the content ID
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/" + str(myself) + "/export/" + str(jobid) + "/status"
        body = self.get(url).text
        results = json.loads(body)
        return results

    def check_export_job_result(self, myself,jobid):
        """
        Using an HTTP client, this starts an export job by passing in the content ID
        """
        time.sleep(DELAY_TIME)
        url = "/v2/content/" + str(myself) + "/export/" + str(jobid) + "/result"
        body = self.get(url).text
        results = json.loads(body)
        return results

### methods ###

if __name__ == '__main__':
    main()
