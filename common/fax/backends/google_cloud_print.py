from google.appengine.api.urlfetch import POST
from common.fax.backends.default import AbstractFaxBackend, FaxStatus
from common.pdf_service import convert_to_pdf
from common.util import get_uuid, safe_fetch
from django.utils import simplejson
import base64
import logging
import time
import urllib

CRLF = '\r\n'
BOUNDARY = get_uuid()

#USERNAME = "printer@waybetter.com"
#PASSWORD = "***REMOVED***"

# The following are used for authentication functions.
REFRESH_TOKEN = '***REMOVED***'
CLIENT_SECRET = '***REMOVED***'
CLIENT_ID = '***REMOVED***'

# The following are used for general backend access.
CLOUDPRINT_URL = 'http://www.google.com/cloudprint'
# CLIENT_NAME should be some string identifier for the client you are writing.
CLIENT_NAME = 'WAYbetter Client'

def GetUrl(url, access_token, data=None):
    """Get URL, with GET or POST depending data, adds Authorization header.

    Args:
      url: Url to access.
      tokens: dictionary of authentication tokens for specific user.
      data: If a POST request, data to be sent with the request.
      cookies: boolean, True = send authentication tokens in cookie headers.
      anonymous: boolean, True = do not send login credentials.
    Returns:
      String: response to the HTTP request.
    """
    logging.debug('Adding authentication credentials to cookie header')
    method = "GET"
    headers = {'Authorization': 'Bearer %s' % access_token}

    if data:
        method = "POST"
        headers['Content-Type'] = 'multipart/form-data;boundary=%s' % BOUNDARY
        logging.info("GetUrl: len(data): %d" % len(data))

    return safe_fetch(url, payload=data, method=method, headers=headers, deadline=60)

def GetPrinters(access_token, proxy=None):
    """Get a list of all printers, including name, id, and proxy.

    Args:
      proxy: name of proxy to filter by.
    Returns:
      dictionary, keys = printer id, values = printer name, and proxy.
    """
    values = {}
    value_tokens = ['"id"', '"name"', '"proxy"']
    for t in value_tokens:
        values[t] = ''

    if proxy:
        response = GetUrl('%s/list?proxy=%s' % (CLOUDPRINT_URL, proxy), access_token)
    else:
        response = GetUrl('%s/search' % CLOUDPRINT_URL, access_token)

    if response:
        return simplejson.loads(response.content)
    else:
        return None


def EncodeMultiPart(fields, files, file_type='application/xml'):
    """Encodes list of parameters and files for HTTP multipart format.

    Args:
      fields: list of tuples containing name and value of parameters.
      files: list of tuples containing param name, filename, and file contents.
      file_type: string if file type different than application/xml.
    Returns:
      A string to be sent as data for the HTTP post request.
    """
    lines = []
    for (key, value) in fields:
        lines.append('--' + BOUNDARY)
        lines.append('Content-Disposition: form-data; name="%s"' % key)
        lines.append('')  # blank line
        lines.append(value)
    for (key, filename, value) in files:
        if key == 'capabilities':
            lines.append('--' + BOUNDARY)
            lines.append('Content-Disposition: form-data; name="%s"' % key)
            lines.append('')  # blank line
            lines.append(value)
            lines.append('--' + BOUNDARY + '--')
    return CRLF.join(lines)


def SubmitJob(printerid, jobtype, data, access_token, title=None):
    """Submit a job to printerid with content of dataUrl.

    Args:
      printerid: string, the printer id to submit the job to.
      jobtype: string, must match the dictionary keys in content and content_type.
      jobsrc: string, points to source for job. Could be a pathname or id string.
    Returns:
      boolean: True = submitted, False = errors.
    """
    if jobtype == 'pdf':
        header = 'data:%s;base64,' % 'application/pdf'
        b64data = header + base64.b64encode(data)
        fdata = b64data
    elif jobtype in ['png', 'jpeg']:
        fdata = data
    else:
        fdata = None

    # Make the title unique for each job, since the printer by default will name
    # the print job file the same as the title.

    if not title:
        datehour = time.strftime('%b%d%H%M', time.localtime())
        title = '%s%s' % (datehour, jobtype)

    content_type = {
        'pdf': 'dataUrl',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        }

    headers = [
        ('printerid', printerid),
        ('title', title),
        ('content', fdata),
        ('contentType', content_type[jobtype])
    ]

    files = [('capabilities', 'capabilities', '{"capabilities":[]}')]
    if jobtype in ['pdf', 'jpeg', 'png']:
        files.append(('content', 'print_job', fdata))
        edata = EncodeMultiPart(headers, files, file_type=content_type[jobtype])
    else:
        edata = EncodeMultiPart(headers, files)

    response = GetUrl('%s/submit' % CLOUDPRINT_URL, access_token, data=edata)
    if response:
        response = simplejson.loads(response.content)
    else:
        response = {"success": False, "message": "GetUrl failed"}

    if not response["success"]:
        logging.error('Print job %s failed with %s', jobtype, response["message"])

    return response


def GetJobs(access_token, printerid=None, jobid=None):
    """Get a list of printer jobs.

    Args:
      printerid: if specified, filter by printer id.
      jobid: if specified, filter by job id.
    Returns:
      dictionary of job id's (key) and printer id's (value).
    """

    if printerid:
        response = GetUrl('%s/fetch?printerid=%s' % (CLOUDPRINT_URL, printerid), access_token)
    elif jobid:
        response = GetUrl('%s/fetch?jobid=%s' % (CLOUDPRINT_URL, jobid), access_token)
    else:
        response = GetUrl('%s/jobs' % CLOUDPRINT_URL, access_token)

    return simplejson.loads(response.content)


def GetAccessToken():
    body = urllib.urlencode({
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        })

    headers = {
        'content-type': 'application/x-www-form-urlencoded',
        }
    res = safe_fetch("https://accounts.google.com/o/oauth2/token", payload=body, headers=headers, method=POST)
    if res:
        json = simplejson.loads(res.content)
        return json['access_token']
    else:
        return None

class GoogleCloudPrintBackend(AbstractFaxBackend):
    @staticmethod
    def send_fax(printerid, html, title):
        pdf = convert_to_pdf(html)
        access_token = GetAccessToken()
        if access_token:
            res = SubmitJob(printerid, "pdf", pdf, access_token, title=title)
            if res["success"]:
                return res["job"]["id"]

        return False

    @staticmethod
    def get_status(job_id):
        access_token = GetAccessToken()
        if access_token:
            res = GetJobs(access_token)
            if res["success"]:
                for job in res["jobs"]:
                    if job["id"] == job_id:
                        return FaxStatus.from_string(job["status"])

        return None

    @staticmethod
    def get_printers():
        access_token = GetAccessToken()
        res = None
        if access_token:
            res = GetPrinters(access_token)

        return res