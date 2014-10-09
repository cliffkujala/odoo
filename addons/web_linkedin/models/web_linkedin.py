import base64
from datetime import datetime, timedelta
import logging
import simplejson
import urllib2
from urlparse import urlparse, urlunparse
import werkzeug.urls

import openerp
from openerp import models, fields, api, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

BASE_API_URL = "https://api.linkedin.com/v1"
company_fields = ["id", "name", "logo-url", "description", "industry", "website-url", "locations", "universal-name"]
people_fields = ["id", "picture-url", "public-profile-url", "first-name", "last-name", "formatted-name", "location", "phone-numbers", "im-accounts", "main-address", "headline", "positions", "summary", "specialties", "email-address"]
_logger = logging.getLogger(__name__)


class except_auth(Exception):
    """ Class for authorization exceptions """
    def __init__(self, name, value, status=None):
        Exception.__init__(self)
        self.name = name
        self.code = 401  # HTTP status code for authorization
        if status is not None:
            self.code = status
        self.args = (self.code, name, value)


class linkedin_users(models.Model):
    _inherit = 'res.users'

    linkedin_token = fields.Char(string="LinkedIn Token")
    linkedin_token_validity = fields.Datetime(string="LinkedIn Token Validity")


class web_linkedin_settings(models.TransientModel):
    _inherit = 'sale.config.settings'

    api_key = fields.Char(string="API Key", help="LinkedIn API Key")
    secret_key = fields.Char(string="Secret Key", help="LinkedIn Secret Key")
    server_domain = fields.Char()
    redirect_url = fields.Char(related='server_domain')
    linkedin_cus_sync = fields.Boolean("Show tutorial to know how to get my 'API key' and my 'Secret key'")
    company_name = fields.Char("Company", default=lambda self:self.env.user.company_id.name)

    @api.model
    def get_default_linkedin(self, fields):
        key = self.env['ir.config_parameter'].get_param("web.linkedin.apikey") or ""
        dom = self.env['ir.config_parameter'].get_param('web.base.url')
        secret_key = self.env['ir.config_parameter'].get_param('web.linkedin.secretkey')
        return {'api_key': key, 'server_domain': dom + "/linkedin/authentication", 'secret_key': secret_key}

    @api.multi
    def set_linkedin(self):
        config_obj = self.env['ir.config_parameter']
        apikey = self.api_key or ""
        secret_key = self.secret_key or ""
        config_obj.set_param("web.linkedin.apikey", apikey, groups=['base.group_users'])
        config_obj.set_param("web.linkedin.secretkey", secret_key, groups=['base.group_users'])


class web_linkedin_fields(models.Model):
    _inherit = 'res.partner'

    @api.model
    def linkedin_check_similar_partner(self, linkedin_datas):
        res = []
        for linkedin_data in linkedin_datas:
            partners = self.env['res.partner'].search_read(["|", ("linkedin_id", "=", linkedin_data['id']),
                    "&", ("linkedin_id", "=", False),
                    "|", ("name", "ilike", linkedin_data['firstName'] + "%" + linkedin_data['lastName']), ("name", "ilike", linkedin_data['lastName'] + "%" + linkedin_data['firstName'])], ["image", "mobile", "phone", "parent_id", "name", "email", "function", "linkedin_id"])
            if partners:
                partner = partners[0]
                if partner['linkedin_id'] and partner['linkedin_id'] != linkedin_data['id']:
                    partner.pop('id')
                if partner['parent_id']:
                    partner['parent_id'] = partner['parent_id'][0]
                for key, val in partner.items():
                    if not val:
                        partner.pop(key)
                res.append(partner)
            else:
                res.append({})
        return res

    linkedin_id = fields.Char(string="LinkedIn ID")
    linkedin_url = fields.Char(string="LinkedIn url")


class linkedin(models.AbstractModel):
    _name = 'linkedin'

    @api.model
    def sync_linkedin_contacts(self, from_url):
        """
            This method will import all first level contact from LinkedIn,
            It may raise AccessError, because user may or may not have create or write access,
            Here if user does not have one of the right from create or write then this method will allow at least for allowed operation,
            AccessError is handled as a special case, AccessError wil not raise exception instead it will return result with warning and status=AccessError.
        """
        sync_result = False
        if not self.need_authorization():
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'x-li-format': 'json'}
            params = {
                'oauth2_access_token': self.env.user.linkedin_token
            }
            connection_uri = "/people/~/connections:{people_fields}".format(people_fields='(' + ','.join(people_fields) + ')')
            status, res = self.with_context(self.env.context).send_request(connection_uri, params=params, headers=headers, type="GET")
            if not isinstance(res, str):
                sync_result = self.update_contacts(res)
            return sync_result
        else:
            return {'status': 'need_auth', 'url': self._get_authorize_uri(from_url=from_url, scope=True)}

    @api.model
    def update_contacts(self, records):
        li_records = dict((d['id'], d) for d in records.get('values', []))
        result = {'_total': len(records.get('values', [])), 'fail_warnings': [], 'status': ''}
        records_to_create, records_to_update = self.check_create_or_update(li_records)
        #Do not raise exception for AccessError, if user doesn't have one of the right from create or write
        try:
            self.create_contacts(records_to_create)
        except openerp.exceptions.AccessError, e:
            result['fail_warnings'].append((e[0], str(len(records_to_create)) + " records are not created\n" + e[1]))
            result['status'] = "AccessError"
        try:
            self.write_contacts(records_to_update)
        except openerp.exceptions.AccessError, e:
            result['fail_warnings'].append((e[0], str(len(records_to_update)) + " records are not updated\n" + e[1]))
            result['status'] = "AccessError"
        return result

    @api.model
    def check_create_or_update(self, records):
        records_to_update = {}
        records_to_create = []
        ids = records.keys()
        read_res = self.env['res.partner'].search_read([('linkedin_id', 'in', ids)], ['linkedin_id'])
        to_update = [x['linkedin_id'] for x in read_res]
        to_create = list(set(ids).difference(to_update))
        for id in to_create:
            records_to_create.append(records.get(id))
        for res in read_res:
            records_to_update[res['id']] = records.get(res['linkedin_id'])
        return records_to_create, records_to_update

    @api.model
    def create_contacts(self, records_to_create):
        for record in records_to_create:
            if record['id'] != 'private':
                vals = self.create_data_dict(record)
                self.env['res.partner'].create(vals)
        return True

    #Currently all fields are re-written
    @api.model
    def write_contacts(self, records_to_update):
        for id, record in records_to_update.iteritems():
            vals = self.create_data_dict(record)
            partner = self.env['res.partner'].search([('id', '=', id)])
            partner.write(vals)
        return True

    @api.model
    def create_data_dict(self, record):
        data_dict = {
            'name': record.get('formattedName', record.get("firstName", "")),
            'linkedin_url': record.get('publicProfileUrl', False),
            'linkedin_id': record.get('id', False),
        }
        #TODO: Should we add: email-address,summary
        positions = (record.get('positions') or {}).get('values', [])
        for position in positions:
            if position.get('isCurrent'):
                data_dict['function'] = position.get('title')
                company_name = False
                if position.get('company'):
                    company_name = position['company'].get('name')
                #To avoid recursion, it is quite possible that connection name and company_name is same
                #in such cases import goes fail meanwhile due to osv exception, hence skipped such connection for parent_id
                if company_name != data_dict['name']:
                    parent = self.env['res.partner'].search([('name', '=', company_name)])
                    if parent:
                        data_dict['parent_id'] = parent.id

        image = record.get('pictureUrl') and self.url2binary(record['pictureUrl']) or False
        data_dict['image'] = image

        phone_numbers = (record.get('phoneNumbers') or {}).get('values', [])
        for phone in phone_numbers:
            if phone.get('phoneType') == 'mobile':
                data_dict['mobile'] = phone['phoneNumber']
            else:
                data_dict['phone'] = phone['phoneNumber']
        return data_dict

    @api.model
    def get_search_popup_data(self, offset=0, limit=5, **kw):
        """
            This method will return all needed data for LinkedIn Search Popup.
            It returns companies(including search by universal name), people, current user data and it may return warnings if any
        """
        result_data = {'warnings': []}
        companies = {}
        people = {}
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'x-li-format': 'json'}
        params = {
            'oauth2_access_token': self.env.user.linkedin_token
        }

        #Profile Information of current user
        profile_uri = "/people/~:(first-name,last-name)"
        status, res = self.with_context(kw.get('local_context') or {}).send_request(profile_uri, params=params, headers=headers, type="GET")
        result_data['current_profile'] = res

        status, companies, warnings = self.get_company_data(offset, limit, params=params, headers=headers, **kw)
        result_data['companies'] = companies
        result_data['warnings'] += warnings
        status, people, warnings = self.get_people_data(offset, limit, params=params, headers=headers, **kw)
        if status:
            result_data['people_status'] = status
        result_data['people'] = people
        result_data['warnings'] += warnings
        return result_data

    @api.model
    def get_company_data(self, offset=0, limit=5, params={}, headers={}, **kw):
        companies = {}
        universal_company = {}
        if not params:
            params = {'oauth2_access_token': self.env.user.linkedin_token}
        if not headers:
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'x-li-format': 'json'}
        #search by universal-name
        if kw.get('search_uid'):
            universal_search_uri = "/companies/universal-name={company_name}:{company_fields}".format(company_name=kw['search_uid'], company_fields='(' + ','.join(company_fields) + ')')
            status, universal_company = self.with_context(kw.get('local_context') or {}).send_request(universal_search_uri, params=params, headers=headers, type="GET")
        #Companies search
        search_params = dict(params.copy(), keywords=kw.get('search_term', "") or "", start=offset, count=limit)
        company_search_uri = "/company-search:(companies:{company_fields})".format(company_fields='(' + ','.join(company_fields) + ')')
        status, companies = self.with_context(kw.get('local_context') or {}).send_request(company_search_uri, params=search_params, headers=headers, type="GET")
        if companies and companies['companies'].get('values') and universal_company:
            companies['companies']['values'].append(universal_company)
        return status, companies, []

    @api.model
    def get_people_data(self, offset=0, limit=5, params={}, headers={}, **kw):
        people = {}
        public_profile = {}
        warnings = []
        if not params:
            params = {'oauth2_access_token': self.env.user.linkedin_token}
        if not headers:
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'x-li-format': 'json'}
        if kw.get('search_uid'):
            #this code may returns 400 bad request error, as per linked API doc the call is proper
            #but generated url may not have proper public url and may raise 400 or 410 status hence added a warning in response and handle warning at client side
            try:
                public_profile_url = werkzeug.url_quote_plus("http://www.linkedin.com/pub/%s" % (kw['search_uid']))
                profile_uri = "/people/url={public_profile_url}:{people_fields}".format(public_profile_url=public_profile_url, people_fields='(' + ','.join(people_fields) + ')')
                status, public_profile = self.with_context(kw.get('local_context') or {}).send_request(profile_uri, params=params, headers=headers, type="GET")

            except urllib2.HTTPError, e:
                if e.code in (400, 410):
                    warnings.append([_('LinkedIn error'), _('LinkedIn is temporary down for the searches by url.')])
                elif e.code in (401):
                    raise e
        search_params = dict(params.copy(), keywords=kw.get('search_term', "") or "", start=offset, count=limit)
        #Note: People search is allowed to only vetted API access request, please go through following link
        #https://help.linkedin.com/app/api-dvr
        people_search_uri = "/people-search:(people:{people_fields})".format(people_fields='(' + ','.join(people_fields) + ')')
        status, people = self.with_context(kw.get('local_context') or {}).send_request(people_search_uri, params=search_params, headers=headers, type="GET")
        if people and people['people'].get('values') and public_profile:
            people['people']['values'].append(public_profile)
        return status, people, warnings

    @api.model
    def get_people_from_company(self, company_universalname, limit, from_url):
        if not self.need_authorization():
            headers = {'Content-type': 'application/json', 'Accept': 'text/plain', 'x-li-format': 'json'}
            params = {
                'oauth2_access_token': self.env.user.linkedin_token,
                'company-name': company_universalname,
                'current-company': 'true',
                'count': limit
            }
            people_criteria_uri = "/people-search:(people:{people_fields})".format(people_fields='(' + ','.join(people_fields) + ')')
            status, res = self.with_context(self.env.context).send_request(people_criteria_uri, params=params, headers=headers, type="GET")
            return res
        else:
            return {'status': 'need_auth', 'url': self._get_authorize_uri(from_url=from_url)}

    @api.model
    def send_request(self, uri, pre_uri=BASE_API_URL, params={}, headers={}, type="GET"):
        result = ""
        status = ""
        try:
            if type.upper() == "GET":
                data = werkzeug.url_encode(params)
                req = urllib2.Request(pre_uri + uri + "?" + data)
                for header_key, header_val in headers.iteritems():
                    req.add_header(header_key, header_val)
            elif type.upper() == 'POST':
                req = urllib2.Request(pre_uri + uri, params, headers)
            else:
                raise ('Method not supported [%s] not in [GET, POST]!' % (type))
            request = urllib2.urlopen(req)
            status = request.getcode()
            if int(status) in (204, 404):  # Page not found, no response
                result = {}
            else:
                content = request.read()
                result = simplejson.loads(content)
        except urllib2.HTTPError, e:
            #Should simply raise exception or simply add logger
            if e.code in (400, 410):
                raise e

            if e.code == 401:
                raise except_auth('AuthorizationError', {'url': self._get_authorize_uri(from_url=self.env.context.get('from_url'),scope=self.env.context.get('scope'))})
            #TODO: Should handle 403 for throttle limit and should display user freindly message
            status = e.code
            _logger.exception("Bad linkedin request : %s !" % e.read())
        except urllib2.URLError, e:
            _logger.exception("Either there is no connection or remote server is down !")
        return (status, result)

    @api.model
    def _get_authorize_uri(self, from_url, scope=False):
        """ This method return the url needed to allow this instance of OpenErp to access linkedin application """
        state_obj = dict(d=scope, f=from_url)
        base_url = self.get_param_parameter('web.base.url')
        client_id = self.get_param_parameter('web.linkedin.apikey')

        params = {
            'response_type': 'code',
            'client_id': client_id,
            'state': simplejson.dumps(state_obj),
            'redirect_uri': base_url + '/linkedin/authentication',
        }

        uri = self.get_uri_oauth(a='authorization') + "?%s" % werkzeug.url_encode(params)
        return uri

    @api.model
    def set_all_tokens(self, token_datas):
        data = {
            'linkedin_token': token_datas.get('access_token'),
            'linkedin_token_validity': datetime.now() + timedelta(seconds=token_datas.get('expires_in'))
        }
        self.env.user.sudo().write(data)

    @api.model
    def need_authorization(self):
        print "\n\ncurrent_user.linkedin_token_validity is ::: ", self.env.user.linkedin_token_validity, datetime.now(), self.env.user.login
        if not self.env.user.linkedin_token_validity or \
                datetime.strptime(self.env.user.linkedin_token_validity.split('.')[0], DEFAULT_SERVER_DATETIME_FORMAT) < (datetime.now() + timedelta(minutes=1)):
            return True
        return False

    @api.model
    def get_param_parameter(self, parameter):
        return self.env['ir.config_parameter'].sudo().get_param(parameter, default=False)

    @api.model
    def test_linkedin_keys(self):
        res = self.get_param_parameter('web.linkedin.apikey') and self.get_param_parameter('web.linkedin.secretkey') and True
        if not res:
            action = self.env['ir.model.data'].get_object_reference('base_setup', 'action_sale_config')[1]
            base_url = self.get_param_parameter('web.base.url')
            res = base_url + '/web?#action=' + str(action),
        return res

    @api.multi
    def get_uri_oauth(self, a=''):  # a = action
        return "https://www.linkedin.com/uas/oauth2/%s" % (a,)

    @api.multi
    def url2binary(self, url):
        """Used exclusively to load images from LinkedIn profiles, must not be used for anything else."""
        _scheme, _netloc, path, params, query, fragment = urlparse(url)
        # media.linkedin.com is the master domain for LinkedIn media (replicated to CDNs),
        # so forcing it should always work and prevents abusing this method to load arbitrary URLs
        try:
            url = urlunparse(('http', 'media.licdn.com', path, params, query, fragment))
            bfile = urllib2.urlopen(url)
        except urllib2.HTTPError, e:
            _logger.exception("Bad URl request : %s !" % e.read())
        return base64.b64encode(bfile.read())
