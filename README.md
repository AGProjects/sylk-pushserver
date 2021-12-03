
# Sylk Pushserver

[Home page](http://sylkserver.com)

Copyright (C) 2021 AG Projects

Sylk Pushserver was designed to act as a central dispatcher for mobile push
notifications inside RTC provider infrastructures.  Both the provider and
the mobile application customer, in the case of a shared infrastructure, can
easily audit problems related to the processing of push notifications.

Authors:

 * Bibiana Rivadeneira
 * Tijmen de Mes


## License

Sylk Pushserver is licensed under GNU General Public License version 3.
[Copy of the license](http://www.fsf.org/licensing/licenses/gpl-3.0.html)


## Deployment scenarios

Sylk Pushserver can be deployed together with WebRTC server applications or
VoIP servers like SIP Proxies and PBXs.  Its main purpose is to act as a
central entity inside RTC provider infrastructures.  Without such a
component, the same functionality must be built inside multiple servers and
as the number of mobile applications increases, the need for such central
component becomes obvious.

### Integration examples

 * OpenSIPS: **config/opensips.cfg**
 * SylkServer: built-in support


## Design

Sylk Pushserver can handle an arbitrary number of different combinations of
push notification service and mobile applications.  It and can be extended
by using Python programming language to support new push notification
services and applications.  Sample applications are provided to handle Sylk
and Linphone mobile applications for Apple and Firebase push notification
services.

For each configured Apple application, the server maintains a persistent
connection by using HTTP/2 over TLS 1.2 and reuses that connection for
sending notifications related to the application.  Latest voip functionality
for iOS 13 or later is also suported.

Each outgoing connection can use its own set of credentials, X.509
certificates and urls.  The connection failures are properly handled and
incoming requests remained queued for later by using a timer dependent on
the payload type.


### Logging

All incoming and outgoing requests, including HTTP headers and bodies, can
be logged for troubleshooting purposes in the system journal and in a
separate log file.  These logs can easily be correlated with the logs from
the server that generated the request by using the call-id key.

Remote HTTP logging of the results is possible so that one or more
third-parties can receive information about the individual push requests and
responses for each application.


## API

Sylk Pushserver expects a json over HTTP POST requests and translates it
into a correspondent outgoing push notifications request to Apple Push
Notifications or Firebase FCM servers.

Json object structure:

```{
'app-id': 'com.agprojects.sylk-ios',
'platform': 'apple',
'token': '6688-71a883fe',
'device-id': 'accc8375125582aae062353',
'call-id': '4dbe8-7a53-42bd-95f3-9a7d43938',
'from': 'alice@example.com',
'from_display_name': 'Alice',
'to': 'bob@biloxi.com',
'media-type':'audio',
'event': 'incoming_session'
'silent': True
'reason': None
}
```

Where:

* `app-id: str`,  id provided by the mobile application (e.g. mobile bundle ID)
* `platform: str`,  'firebase', 'android', 'apple' or 'ios'
* `token: str`,  destination device token,
    * *iOS device tokens* are strings with 64 hexadecimal symbols
    * *Android device push tokens* can differ in length`.
* `device-id: str`,  the device that generated the token
* `call-id: str`,  the unique session id for each call
* `from: str`,  address of the caller
* `from_display_name`, (mandatory)*, display name of the caller
* `to`,  address of the callee
* `media-type: str`:  'audio', 'video', 'chat', 'sms' or 'file-transfer'
* `silent: bool`: *(optional, default `True`)* True for silent notification
* `reason:str`: *(optional)* Cancel reason
* `event: str`,  type of event:
    * For *Sylk app*  must be 'incoming_session', 'incoming_conference' or 'cancel'
    * For *Linphone app*  must be 'incoming_session'

The response is a json with the following structure:

```
{
'code': 'a numeric code equal to the HTTP response code',
'description': 'a detailed text description',
'data' : {}
}
```

*data* contains an arbitrary dictionary with a structure depending on the
request type and the remote server response.

### V2

API version 2 supports storage of the push tokens in a Apache Cassandra Cluster
or locally in a pickle file. The elements in the API methods are the same type
and values as in API version 1. The API has the following methods:

**POST** `/v2/tokens/{account}` - Stores a token for `{account}`
```
{
    "app-id": "string",
    "platform": "string",
    "token": "string",
    "device-id": "string",
    "silent": true,
    "user-agent": "string"
}
```

**DELETE** `/v2/tokens/{account}` - Removes a token for `{account}`

```
{
    "app-id": "string",
    "device-id": "string"
}
```

**POST** `/v2/tokens/{account}/push` - Sends a push notification(s) for `{account}`

```
{
    "event": "string",
    "call-id": "string",
    "from": "string",
    "from-display-name": "string",
    "to": "string",
    "media-type": "string",
    "reason": "string"
}
```

**POST** `/v2/tokens/{account}/push/{device}` - Sends a push notification for `{account}` and `{device}`

```
{
    "event": "string",
    "call-id": "string",
    "from": "string",
    "from-display-name": "string",
    "to": "string",
    "media-type": "string",
    "reason": "string"
}
```

### Sample client code

* See [sylk-pushclient](scripts/sylk-pushclient)
* See [sylk-pushclient-v2](scripts/sylk-pushclient-v2)


### External APIs

For documentation related to the API used by Apple and Firebase push
notifications services you must consult their respective websites.  For
reference, the following APIs were used for developing the server, but these
links may change:

 * [Sending Apple VoIp notifications](https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/sending_notification_requests_to_apns)
 * [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging)
 * [FCM migration from legacy HTTP to HTTP v1](https://firebase.google.com/docs/cloud-messaging/migrate-v1)


### Apple Certificate

Go to Apple developer website

https://developer.apple.com/account/resources/identifiers/list

Go to Identifiers section

Select the app id

Scroll down to Push notifications

Click Configure

Generate a certificate. 

Export the certificate to pk12 format from Keychain.

Convert the cartificate and private key to .pem format:

openssl pkcs12 -in Certificates.p12   -nocerts -out sylk.privateKey.pem
openssl pkcs12 -in Certificates.p12 -clcerts -nokeys -out sylk.pem

Remove the passcode from the private key:

openssl rsa -in sylk.privateKey.pem -out sylk.key

Use sylk.pem and sylk.key inside applications.ini config file.


## Installation

### As a Debian package

Install the AG Projects debian software signing key:

wget http://download.ag-projects.com/agp-debian-gpg.key

sudo apt-key add agp-debian-gpg.key

Add these repository matching your distribution to /etc/apt/sources.list:

https://docs-new.sipthor.net/w/debian_package_repositories/

Update the list of available packages:

sudo apt-get update

sudo apt-get install sylk-pushserver


### From source

The source code is managed using darcs version control tool. The darcs
repository can be fetched with:

darcs clone http://devel.ag-projects.com/repositories/sylk-pushserver

Alternatively, one can download a tar archive from:

http://download.ag-projects.com/SylkPushserver/

Install Python dependencies:

`pip3 install -r requirements.txt`

`python3 setup.py install`


### Building Debian package

Install building dependencies:

```
sudo apt install dh-virtualenv debhelper libsystemd-dev dh-python python3-dev python3-setuptools python3-pip
```

Build the package:

```
python setup.py sdist
cd dist
tar zxvf *.tar.gz
cd sylk_pushserver-?.?.?
debuild
```

To install the debian package manually:

```
sudo dpkg -i sylk-pushserver_1.0.0_all.deb
sudo apt --fix-broken install
```
## Configuration

There are two configurations files.

 * general.ini

Contains the general server settings.

 * applications.ini

Contains the settings for each mobile application, *see
config/applications.ini.sample*.  Chages to this file cause the server to
autamtically reload it, there is no need to restart the server.


## Remote logging

Remote logging is done using a POST request over HTTP with a json containg
both the original request and the final response of the push notification.

```{
'request': push_request,
'response': push_response
}
```

Where :

 * push_request is the original json payload received by this server
 * push_response is a json with the following format:

```{
'code': code,                # http response code from PNS
'description': description,  # detail description of the response from the PNS
'push_url': push_url,        # the final URL of the outgoing push notification
'incoming_body': {...},      # the original request body received by the server
'outgoing_headers': {...}.   # the outgoing request headers sent to the PNS
'outgoing_body': {...}       # the outgoing request body sent to the PNS
}
```

The returned result should be a json with a consistent key.  The key can be
defined in the application.ini for each application.  If the key is set then
its value will be logged which can make troubleshooting easier.


## Custom applications

Custom applications can be written in Python by subclassing existing template classes.

Define the directory for custom applications in `general.ini` file:

 `extra_applications_dir` = `/etc/sylk-pushserver/applications`

Copy config/applications/myapp.py to the extra_applications_dir and
overwrite its functions.

In `applications.ini` file set app_type for the custom applications:

```
`app_type` = *myapp*
```

## Custom Push services

Custom PNS can be written in Python by subclassing existing template classes.

Define the directory for custom push services in `general.ini` file:

 `extra_pns_dir` = `/etc/sylk-pushserver/pns`

Copy config/pns/mypns.py to the extra_pns dir and overwrite its classes.

In `applications.ini` file set app_type for the custom applications:

```
`app_platform` = *mypns*
```


## Running the server

### From the source code

`./sylk-pushserver --config_dir <path-to-config-directory>`

If the config_dir directory is not specified, the following paths are searched for:

  * /etc/sylk-pushserver
  *./config

For more command line options use -h.


### Debian package

```
sudo systemctl start sylk-pushserver
```

### Testing

For testing the server scripts/sylk-pushclient can be used.


## Compatibility

The server is developed in Python 3 and was tested on Debian Buster 10.


## Reporting bugs

You may report bugs to [SIP Beyond VoIP mailing list](http://lists.ag-projects.com/pipermail/sipbeyondvoip/)

