import requests
import os
import re
import json

WIT_API_HOST = os.getenv('WIT_URL', 'https://api.wit.ai')
WIT_API_VER  = os.getenv('WIT_API_VER', '20160330')
DEFAULT_MAX_STEPS = 5

def prettyprint(data, indent = 4):
    """Nicer version of pprint (which is actually kind of ugly)

    Note: assumes that input data can be dumped to json (typically a list or dict)
    """
    pattern = re.compile(r'^', re.MULTILINE)
    spaces = ' ' * indent
    print re.sub(pattern, spaces, json.dumps(data, indent=indent, sort_keys=True))

class WitError(Exception):
    def __init__(self, msg, resp=None):
        self.args = (msg, resp)
        self.message = msg
        self.resp = resp

def req(access_token, meth, path, params, **kwargs):
    rsp = requests.request(
        meth,
        WIT_API_HOST + path,
        headers={
            'authorization': 'Bearer ' + access_token,
            'accept': 'application/vnd.wit.' + WIT_API_VER + '+json'
        },
        params=params,
        **kwargs
    )
    if rsp.status_code > 200:
        raise WitError('Wit responded with status: ' + str(rsp.status_code) +
                       ' (' + rsp.reason + ')', rsp)
    json = rsp.json()
    if 'error' in json:
        raise WitError('Wit responded with an error: ' + json['error'])
    return json

def validate_actions(actions):
    learn_more = 'Learn more at https://wit.ai/docs/quickstart'
    if not isinstance(actions, dict):
        raise WitError('The second parameter should be a dictionary.')
    for action in ['say', 'merge', 'error']:
        if action not in actions:
            raise WitError('The \'' + action + '\' action is missing. ' +
                           learn_more)
    for action in actions.keys():
        if not hasattr(actions[action], '__call__'):
            raise TypeError('The \'' + action +
                            '\' action should be a function.')
    return actions

class Wit:
    access_token = None
    actions = {}

    def __init__(self, access_token, actions):
        self.access_token = access_token
        self.actions = validate_actions(actions)

    ####################
    # message/converse #
    ####################

    def message(self, msg, context={}, **kwargs):
        params = {}
        if msg:
            params['q'] = msg
        params.update(kwargs)
        return req(self.access_token, 'GET', '/message', params, json=context)

    def converse(self, session_id, message, context={}, **kwargs):
        params = {'session_id': session_id}
        if message:
            params['q'] = message
        params.update(kwargs)
        return req(self.access_token, 'POST', '/converse', params, json=context)

    def __run_actions(self, session_id, message, context, max_steps,
                      user_message):
        if max_steps <= 0:
            raise WitError('max iterations reached')
        rst = self.converse(session_id, message, context)
        if 'type' not in rst:
            raise WitError('couldn\'t find type in Wit response')
        if rst['type'] == 'stop':
            return context
        if rst['type'] == 'msg':
            if 'say' not in self.actions:
                raise WitError('unknown action: say')
            print('Executing say with: {}'.format(rst['msg']))
            self.actions['say'](session_id, dict(context), rst['msg'])
        elif rst['type'] == 'merge':
            if 'merge' not in self.actions:
                raise WitError('unknown action: merge')
            print('Executing merge')
            context = self.actions['merge'](session_id, dict(context),
                                            rst['entities'], user_message)
            if context is None:
                print('WARN missing context - did you forget to return it?')
                context = {}
        elif rst['type'] == 'action':
            if rst['action'] not in self.actions:
                raise WitError('unknown action: ' + rst['action'])
            print('Executing action {}'.format(rst['action']))
            context = self.actions[rst['action']](session_id, dict(context))
            if context is None:
                print('WARN missing context - did you forget to return it?')
                context = {}
        elif rst['type'] == 'error':
            if 'error' not in self.actions:
                raise WitError('unknown action: error')
            print('Executing error')
            self.actions['error'](session_id, dict(context),
                                  WitError('Oops, I don\'t know what to do.'))
        else:
            raise WitError('unknown type: ' + rst['type'])
        return self.__run_actions(session_id, None, context, max_steps - 1,
                                  user_message)

    def run_actions(self, session_id, message, context={},
                    max_steps=DEFAULT_MAX_STEPS):
        return self.__run_actions(session_id, message, context, max_steps,
                                  message)

    ###########
    # intents #
    ###########

    def list_intents(self):
        params = {}
        return req(self.access_token, 'GET', '/intents', params)

    def get_intent(self, intent_id):
        params = {}
        uri_path = '/intents/' + intent_id
        return req(self.access_token, 'GET', uri_path, params)

    def post_intent(self, intent):
        params = {}
        return req(self.access_token, 'POST', '/intents', params, json=intent)

    def put_intent(self, intent):
        params = {}
        intent_id = intent.pop('name', None)
        if not intent_id:
            return False
        uri_path = '/intents/' + intent_id
        return req(self.access_token, 'PUT', uri_path, params, json=intent)

    def delete_intent(self, intent_id):
        params = {}
        uri_path = '/intents/' + intent_id
        return req(self.access_token, 'DELETE', uri_path, params)

    ############
    # entities #
    ############

    def list_entities(self):
        params = {}
        return req(self.access_token, 'GET', '/entities', params)

    def get_entity(self, entity_id):
        params = {}
        uri_path = '/entities/' + entity_id
        return req(self.access_token, 'GET', uri_path, params)

    def post_entity(self, entity):
        params = {}
        return req(self.access_token, 'POST', '/entities', params, json=entity)

    def put_entity(self, entity):
        params = {}
        entity_id = entity.pop('id', None)
        if not entity_id:
            return False
        uri_path = '/entities/' + entity_id
        return req(self.access_token, 'PUT', uri_path, params, json=entity)

    def post_entity_value(self, entity_id, value):
        params = {}
        uri_path = '/entities/' + entity_id + '/values'
        return req(self.access_token, 'POST', uri_path, params, json=value)

    def delete_entity(self, entity_id):
        params = {}
        uri_path = '/entities/' + entity_id
        return req(self.access_token, 'DELETE', uri_path, params)
