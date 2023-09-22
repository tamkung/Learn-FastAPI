from sentry_sdk import configure_scope
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(process)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S %Z00",
)
LOGGER = logging.getLogger("python-logstash-logger")
LOGGER.setLevel(logging.INFO)

class sentryLog(object):
    def __init__(self,
                 service=None,
                 flow=None,
                 step=None,
                 func=None,
                 user_id=None,
                 email=None,
                 detail=None,
                 metadata=None,
                 status=None,
                 event_id=None,
                 ip=None):
        self.service = "emt-tool"
        self.flow = flow
        self.step = step
        self.func = func
        self.user_id = user_id 
        self.email = email 
        self.detail = detail
        self.metadata = {}
        self.status = status
        self.event_id = event_id
        self.ip = ip 


    def _error(self):
        with configure_scope() as scope:
            scope.set_tag("service", "emt-tool")
            scope.set_tag("status", self.status)
            scope.set_tag("event_id", self.event_id)
            scope.set_tag("ip", self.ip)
            scope.user = {
                "email": self.email,
                "id": self.user_id
            }
            self.LOGGER.error(
                "service:%s flow:%s step:%s func:%s user_id:%s email:%s detail:%s metadata:%s"
                % (self.service, self.flow, self.step, self.func, self.user_id,
                self.email, self.detail, self.metadata))

    def _info(self):
        self.LOGGER.info(
            "service:%s flow:%s step:%s func:%s user_id:%s email:%s detail:%s metadata:%s"
            % (self.service, self.flow, self.step, self.func, self.user_id,
               self.email, self.detail, self.metadata))

    def _debug(self, message):
        self.LOGGER.debug(message)
