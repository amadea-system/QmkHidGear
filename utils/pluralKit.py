"""

"""
from __future__ import annotations

import logging
from typing import Optional, Dict, List, Union
from datetime import date, datetime

import requests


log = logging.getLogger(__name__)

base_url = "https://api.pluralkit.me/v1"
pk_gateway_base_url: Optional[str] = None  # Internal Plural Kit API Gateway.

# --- Web Methods --- #


def api_get(url: str, authorization=None):
    headers = None
    if authorization:
        headers = {'Authorization': authorization}

    with requests.get(f"{base_url}{url}", headers=headers) as resp:
        if resp.status_code == 404:
            raise NotFound
        elif resp.status_code == 403:
            raise Unauthorized
        json = resp.json()
    return json


def gateway_api_get(url: str, authorization=None):

    if pk_gateway_base_url is None:
        log.warning(f"'pk_gateway_base_url' was not defined! Falling back on api.pluralkit.me/")
        return api_get(url, authorization)

    headers = None
    if authorization:
        headers = {'Authorization': authorization}

    with requests.get(f"{pk_gateway_base_url}{url}", headers=headers) as resp:
        if resp.status_code == 404:
            raise NotFound
        elif resp.status_code == 403:
            raise Unauthorized
        json = resp.json()
    return json


def api_post(url: str, payload, authorization: Optional[str] = None):
    headers = None
    if authorization:
        headers = {'Authorization': authorization}

    with requests.post(f"{base_url}{url}", json=payload, headers=headers) as resp:
        if resp.status_code == 404:
            raise NotFound
        elif resp.status_code == 401:
            raise Unauthorized
        elif resp.status_code == 400:
            raise MembersAlreadyFronting
        elif resp.status_code == 204:
            return True  # The switch was logged.
        json = resp.json()
    return json


# --- Classes --- #

class Members:
    members: List[Member]

    def __init__(self, members: List[Member]):
        self.members = members

    def __repr__(self):
        return f"<Members Members={self.members}"

    def __str__(self):
        return f"<Members Members={self.members}"

    def __setitem__(self, index, value):
        self.members[index] = value

    def __getitem__(self, index):
        return self.members[index]

    def __len__(self):
        return len(self.members)

    def __iter__(self):
        ''' Returns the Iterator object '''
        return iter(self.members)

    def append(self, item):
        self.members.append(item)

    def remove(self, item):
        self.members.remove(item)

    @staticmethod
    def get_by_hid(hid: str, authorization=None):
        json = api_get(f"/s/{hid}/members", authorization)
        members = json

        return Members([Member(**member) for member in members])


class Fronters:
    timestamp: datetime
    members: List[Member]


    def __init__(self, timestamp, members):
        self.timestamp = timestamp
        self.members = [Member(**member) for member in members]  # Todo: replace with Members Object


    def __repr__(self):
        return f"<Fronters timestamp={self.timestamp} members={self.members}"


    def __str__(self):
        return f"<Fronters timestamp={self.timestamp} members={self.members}"


    @staticmethod
    def get_by_hid(hid: str, authorization=None):
        json = api_get(f"/s/{hid}/fronters", authorization)
        fronters = json
        return Fronters(**fronters)


class System:
    hid: str
    name: str
    description: str
    tag: str
    avatar_url: str
    created: str
    tz: str
    api_token: str
    description_privacy: Optional[str]
    member_list_privacy: Optional[str]
    front_privacy: Optional[str]
    front_history_privacy: Optional[str]


    def __init__(self, id, created, name=None, description=None, tag=None, avatar_url=None, tz=None,
                 description_privacy=None, member_list_privacy=None, front_privacy=None, front_history_privacy=None):
        self.hid = id
        self.created = created
        self.name = name
        self.description = description
        self.tag = tag
        self.avatar_url = avatar_url
        self.tz = tz
        self.api_token = None
        self.description_privacy = description_privacy
        self.member_list_privacy = member_list_privacy
        self.front_privacy = front_privacy
        self.front_history_privacy = front_history_privacy


    def __repr__(self):
        return f"<System hid={self.hid} name={self.name} description={self.description} tag={self.tag} avatar_url={self.avatar_url} created={self.created} tz={self.tz}"


    def __str__(self):
        return f"<System hid={self.hid} name={self.name} description={self.description} tag={self.tag} avatar_url={self.avatar_url} created={self.created} tz={self.tz}"


    def members(self):
        json = api_get(f"/s/{self.hid}/members", self.api_token)
        members = json
        m = []
        for member in members:
            m.append(Member(**member))
        return m


    def fronters(self):
        json = api_get(f"/s/{self.hid}/fronters", self.api_token)
        fronters = json
        return Fronters(**fronters)


    def cached_fronters(self):
        json = gateway_api_get(f"/s/amadea/fronters", self.api_token)
        fronters = json
        return Fronters(**fronters)


    @staticmethod
    def get_by_hid(hid, authorization=None):
        json = api_get(f"/s/{hid}", authorization)
        sys = json
        system = System(**sys)
        system.api_token = authorization
        return system


    @staticmethod
    def get_by_account(account, authorization=None):
        json = api_get(f"/a/{account}", authorization)
        sys = json
        system = System(**sys)
        system.api_token = authorization
        return system

    def set_fronters(self, members: Optional[Union[List[str]]]):
        if members is None or members == []:
            payload = {'members': []}
        else:
            payload = {'members': members}

        status = api_post("/s/switches", payload, self.api_token)
        return status




class ProxyTag:
    prefix: str
    suffix: str


    def __init__(self, prefix=None, suffix=None):
        if prefix is None and suffix is None:
            raise NoProxyError
        else:
            self.prefix = prefix
            self.suffix = suffix


    def __repr__(self):
        return f"<ProxyTag prefix={self.prefix} suffix={self.suffix}"


    def __str__(self):
        return f"<ProxyTag prefix={self.prefix} suffix={self.suffix}"


class Member:
    hid: str
    name: str
    color: str
    display_name: str
    birthday: date
    pronouns: str
    avatar_url: str
    description: str
    proxy_tags: List
    keep_proxy: bool
    privacy: str
    visibility: str
    name_privacy: str
    description_privacy: str
    avatar_privacy: str
    birthday_privacy: str
    pronoun_privacy: str
    metadata_privacy: str
    created: datetime

    prefix: str
    suffix: str

    system: int
    sid: str

    def __init__(self, keep_proxy=None, proxy_tags=None, id=None, name=None, display_name=None, system=None, created=None, color=None,
                 avatar_url=None, birthday=None, pronouns=None, description=None, prefix=None, suffix=None, sid=None, privacy=None,
                 visibility=None, name_privacy=None, description_privacy=None, avatar_privacy=None, birthday_privacy=None,
                 pronoun_privacy=None, metadata_privacy=None):
        self.hid = id
        self.name = name
        self.display_name = display_name
        self.system = system
        self.created = created
        self.color = color
        self.avatar_url = avatar_url
        self.birthday = birthday
        self.pronouns = pronouns
        self.description = description
        self.prefix = prefix
        self.suffix = suffix
        self.proxy_tags = []
        self.keep_proxy = keep_proxy
        self.sid = sid
        self.privacy = privacy

        self.visibility = visibility
        self.name_privacy = name_privacy
        self.description_privacy = description_privacy
        self.avatar_privacy = avatar_privacy
        self.birthday_privacy = birthday_privacy
        self.pronoun_privacy = pronoun_privacy
        self.metadata_privacy = metadata_privacy

        if proxy_tags is not None:
            for proxy_tag in proxy_tags:
                self.proxy_tags.append(ProxyTag(proxy_tag['prefix'], proxy_tag['suffix']))

    def __repr__(self):
        return f"<Member hid={self.hid} name={self.name} display_name={self.display_name} system={self.system} created={self.created} color={self.color} avatar_url={self.avatar_url} birthday={self.birthday} pronouns={self.pronouns} description={self.description} prefix={self.prefix} suffix={self.suffix} proxy_tags={self.proxy_tags} keep_proxy={self.keep_proxy}"

    def __str__(self):
        return f"<Member hid={self.hid} name={self.name} display_name={self.display_name} system={self.system} created={self.created} color={self.color} avatar_url={self.avatar_url} birthday={self.birthday} pronouns={self.pronouns} description={self.description} prefix={self.prefix} suffix={self.suffix} proxy_tags={self.proxy_tags} keep_proxy={self.keep_proxy}"

    # TODO: Determine if lazily compairing just the id's is enough or if we need to compare other vars as well
    def __eq__(self, other):
        if isinstance(other, Member):
            if self.hid == other.hid:
                return True
        return False

    @property
    def proxied_name(self):
        return self.display_name or self.name

    @staticmethod
    def get_by_hid(hid, authorization=None):
        json = api_get(f"/m/{hid}")
        member = json
        return Member(**member)

# --- Exceptions --- #


class PluralKitError(Exception):
    pass

class APIError(PluralKitError):
    pass

class NotFound(APIError):
    pass

class Unauthorized(APIError):
    pass

class NeedsAuthorization(APIError):
    pass

class NoProxyError(PluralKitError):
    pass

class MembersAlreadyFronting(PluralKitError):
    pass


if __name__ == '__main__':
    pk_token = "TEST TOKEN HERE"

    test_sys = System.get_by_hid("TEST SYS ID HERE", authorization=pk_token)
    test_sys_front = Fronters.get_by_hid("TEST SYS ID HERE", authorization=pk_token)
    json = test_sys.set_fronters([])


    print("Nyaaa")