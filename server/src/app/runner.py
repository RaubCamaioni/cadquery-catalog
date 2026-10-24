def runner():
    import uvicorn
    from app.app import app

    from app import ENVIRONMENT

    from uvicorn.config import LOGGING_CONFIG

    # the sandbox core logs to "sandboxcore": print it with uvicorn's own messages
    core = {"handlers": ["default"], "level": "INFO", "propagate": False}
    log_config = {**LOGGING_CONFIG, "loggers": {**LOGGING_CONFIG["loggers"], "sandboxcore": core}}

    # root_path makes request.scope["root_path"] the mount prefix; routing still sees the paths below it
    uvicorn.run(app, host="0.0.0.0", port=8080, root_path=ENVIRONMENT.ROOT_PATH, log_config=log_config)
