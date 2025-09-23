from settings import settings
import logging

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)
    log.info('uvicorn_port = %s', settings.uvicorn_port)
    log.info('frontend_port = %s', settings.frontend_port)
    log.info('use_dev_frontend = %s', settings.use_dev_frontend)
    log.info('require_contact_profile = %s', settings.require_contact_profile)
