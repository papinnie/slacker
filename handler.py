import os
import re
import yaml
import slack
import slack.chat
import importlib
from aiosmtpd.handlers import Message


class MessageHandler(Message):
    def __init__(self, *args, **kargs):
        Message.__init__(self, *args, **kargs)

        config = os.getenv('CONFIG', '/etc/slacker/config.yml')
        print(config)
        if not os.path.exists(config):
            print('Config doesn\'t exists!')
            exit(1)

        # load processor.py
        # and body is processed by a processor() function
        self.processor = lambda x: return x
        processor = importlib.util.find_spec("processor")
        if processor:
            processor_module = importlib.util.module_from_spec(processor)
            processor.loader.exec_module(processor_module)
            self.processor = processor_module.processor

        self.config = yaml.load(open(config))

    def handle_message(self, message):
        """ This method will be called by aiosmtpd server when new mail will
            arrived.
        """
        options = self.process_rules(message)

        print('matched', options)
        self.send_to_slack(self.extract_text(message, options), **options)

        if options['debug']:
            self.send_to_slack('DEBUG: ' + str(message), **options)

    def process_rules(self, message):
        """ Check every rule from config and returns options from matched
        """
        default = self.config['default']

        fields = {
            'from': message['From'],
            'to': message['To'],
            'subject': message['Subject'],
            'body': message.get_payload()
        }

        print(fields)

        for rule in self.config['rules']:
            # TODO: better handling of None values than just str(value)
            tests = (
                re.match(rule[field], str(value))
                for field, value in fields.items() if field in rule
            )

            if all(tests):
                options = default.copy()
                options.update(rule['options'])
                return options

        return default

    def extract_text(self, message, options):
        fmt = self.config['default'].get('format', '%(body)s')
        body = message.get_payload()
        subject = message['Subject']

        # body replace
        if 'exclude' in options:
            for regexp in options['exclude']:
                body = re.sub(regexp, '', body)

        # body customized processor
        body = self.processor(body)

        return fmt % dict(body=body, subject=subject)

    def send_to_slack(self, text, **options):
        print('sending to slack', text, options)

        slack.api_token = options['slack_token']
        slack.chat.post_message(
            options['channel'],
            text,
            username=options['username'],
            icon_url=options['icon_url']
        )
