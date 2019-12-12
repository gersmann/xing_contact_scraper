# -*- coding: utf-8 -*-
import scrapy
import json
from xing import config

class ContactsSpider(scrapy.Spider):
    name = 'contacts'
    allowed_domains = ['xing.com']
    start_urls = ['http://login.xing.com/']

    def parse(self, response):
        self.login_csrf = response.headers.getlist('Set-Cookie')[0].decode().split(';')[0].split('=')[1]
        return scrapy.http.JSONRequest(
            url="https://login.xing.com/xhr/login",
            data={'username': config.username, 'password': config.password, 'perm': '1'},
            headers={'x-csrf-token': self.login_csrf, 'content-type': 'application/json', 'accept': 'application/json'},
            callback=self.after_login
        )

    def after_login(self, response):
        return scrapy.Request(url=json.loads(response.body)['target'], meta={'handle_httpstatus_list': [302]}, callback=self.after_redirect)

    def after_redirect(self, response):
        self.site_csrf = response.headers.getlist('Set-Cookie')[0].decode().split(';')[0].split('=')[1]
        return scrapy.http.JSONRequest(
            url=f'https://www.xing.com/contacts/contacts.json?page=1&initial=&order_by=first_name&no_tags=&query=&view_type=condensed&custom_url=true',
            callback=self.fetch_contacts)

    def fetch_contacts(self, response):
        json_response = json.loads(response.body)

        graph_string = '{"operationName":"getXingId","variables":{"profileId":"","actionsFilter":["ADD_CONTACT","ADVERTISE_PROFILE","BLOCK_USER","BOOKMARK_USER","CONFIRM_CONTACT","EDIT_XING_ID","FOLLOW","INVITE_GROUP","OPEN_INSIDER_COLLECTION","OPEN_SETTINGS","OPEN_XTM","PRINT","REPORT_PROFILE","SEND_MESSAGE","SHARE","SHOW_CONTACT_DETAILS","UNBLOCK_USER","UNFOLLOW"]}}'
        graph_json = json.loads(graph_string)
        graph_json['query'] = 'query getXingId($profileId: SlugOrID!, $actionsFilter: [AvailableAction!]) {\n  profileModules(id: $profileId) {\n    __typename\n    xingIdModule(actionsFilter: $actionsFilter) {\n      xingId {\n        status {\n          localizationValue\n          __typename\n        }\n        __typename\n      }\n      __typename\n      ...xingIdContactDetails\n      ...xingIdModuleCta\n    }\n  }\n}\n\nfragment xingIdContactDetails on XingIdModule {\n  contactDetails {\n    business {\n      address {\n        city\n        country {\n          countryCode\n          name: localizationValue\n          __typename\n        }\n        province {\n          id\n          canonicalName\n          name: localizationValue\n          __typename\n        }\n        street\n        zip\n        __typename\n      }\n      email\n      fax {\n        phoneNumber\n        __typename\n      }\n      mobile {\n        phoneNumber\n        __typename\n      }\n      phone {\n        phoneNumber\n        __typename\n      }\n      __typename\n    }\n    private {\n      address {\n        city\n        country {\n          countryCode\n          name: localizationValue\n          __typename\n        }\n        province {\n          id\n          canonicalName\n          name: localizationValue\n          __typename\n        }\n        street\n        zip\n        __typename\n      }\n      email\n      fax {\n        phoneNumber\n        __typename\n      }\n      mobile {\n        phoneNumber\n        __typename\n      }\n      phone {\n        phoneNumber\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n\nfragment xingIdModuleCta on XingIdModule {\n  actions {\n    __typename\n    label\n  }\n  __typename\n}\n'

        for user in json_response['contacts']:
            page_name = user['page_name']
            graph_json['variables']['profileId'] = page_name

            details = scrapy.http.JSONRequest(
                url='https://www.xing.com/xing-one/api',
                method='POST',
                data=graph_json,
                headers={'X-CSRF-Token': self.site_csrf, 'XING-ONE-PREVIEW': 'true'},
                callback=self.fetch_details
            )
            details.meta['user_first_name'] = user['first_name']
            details.meta['user_last_name'] = user['last_name']
            details.meta['user_company'] = user['occupation_org']

            yield details

        current_page = json_response['paginator']['current_page']
        total_pages = json_response['paginator']['total_pages']

        if (current_page != total_pages) and (current_page != config.page_limit):
            yield scrapy.http.JSONRequest(
                url=f'https://www.xing.com/contacts/contacts.json?page={current_page+1}&initial=&order_by=first_name&no_tags=&query=&view_type=condensed&custom_url=true&_=1575990276751',
                callback=self.fetch_contacts)

    def fetch_details(self, response):
        json_response = json.loads(response.body)
        contact_details = json_response['data']['profileModules']['xingIdModule']['contactDetails']

        business_email = None
        private_email = None

        try:
            business_email = contact_details['business']['email']
        except KeyError:
            pass
        try:
            private_email = contact_details['business']['email']
        except KeyError:
            pass

        yield {
            'First Name': response.meta.get('user_first_name'),
            'Last Name': response.meta.get('user_last_name'),
            'Company': response.meta.get('user_company'),
            'E-mail Address': business_email,
            'E-mail 2 Address': private_email
        }


