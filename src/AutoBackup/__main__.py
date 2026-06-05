"""TODO:
Intended to be run at device startup, then:
-> Starts all backup schedulers
-> Starts the flask webapp
-> Give a way to open a webview window to the flask webapp
    - make sure its decoupled from flask (use url instead of app object), so that don't need to keep running webview in background
-> Give a way to exit (stop all schedulers and stop flask webapp)
"""