# Problem statement
To see your way of coding and thinking about the problem and we would like you to write a python program that would satisfy the following: 
- be an API answering "questions" with a payload being a json
- call to an arbitrary external executable
- handle custom msgs for #400, #404, #500, #501, etc.
- handle new requests while performing a blocking call
- graceful shutdown
- sample unit test(s)
 What could be a sample program that would satisfy the above conditions:
 Make a call to an API with a json structure containing a folder name and parameters to list files from the folder. The parameters could define a filter or just be passed over to `ls`. To simulate a blocking call, make the code listing files in a directory sleep for 5 seconds. Log and respond with a custom msg if a folder does not exist, you have no rights to read it or simply the URL one tries to reach is not reachable. If SIGINT is sent to the API serving script, then make sure you handle all outstanding requests before shutting down. 
Whenever you are ready put your solution on a github, or any similar service, so we could clone it and run it locally. Then we will have a look at it and inform about the next steps. 
----

# My take on the problem

Let’s write a solution for the problem statement above with the following variation : 
We want a service answering to an API call to retrieve quotes from a set of dictionary files stored in the file system. 
The requester send a search string and some parameters within a json structure
the underlying service will perform a grep in the dictionary files and answer with either a json structure holding the results or with an error message if not possible (details later)

In order to implement this as a lightweight service and due to the requirement to support concurrent calls (potentially blocking) on the IO side several options are available. 
As a web framework I chose Flask for the simplicity of its setup.
For the concurrency requirements either multithreading or asyncio.
Finally, when using flask and asyncio together, an integrated solution exists in the Quart web framework, a flask fork which natively support asyncio.

# Initial analysis

Let’s write a solution for the problem statement above with the following variation : 
We want a service answering to an API call to retrieve text quotes from a set of dictionary files stored in the file system. 
The requester send a search string and some parameters within a json structure
the underlying service will perform a grep in the dictionary files and answer with either a json structure holding the results or with an error message if not possible (details later)

In order to implement this as a lightweight service and due to the requirement to support concurrent calls (potentially blocking) on the IO side several options are available. 
As a web framework I would chose Flask for the simplicity of its setup.
For the concurrency requirements either multithreading or asyncio.
Finally, when using flask and asyncio together, an integrated solution exists in the Quart web framework, a Flask fork which natively support asyncio.

## Core function

The core function implements calling grep on a set of files indicated by a specific dictionary name (if nothing is indicated a default one is used), with :

	a search term provided 

	and some options:

		number of lines before and after the quotes to be returned (default = 0)
		number of results to be provided (defaults = all)
	
Additionally, an action to get all results from the file will be provided by the API.

## API structure

the API is implemented using POST methods with a json payload.
to use it send a POST request at /api/v1/json with the following data:


“action” : “all”
	will provide a full dump of the dictionary

“action” : “search”
	requires an additional required parameter:
	“term” : *the term to be searched*, string

	and some optional parameters:
		“nresults”: *number of results*, int (default = all if parameter not provided or <= 0)
		“n_before” : *lines to be quoted before*, int
		“n_after” : *lines to be quoted after*, int

optional parameter for all actions:
	“dictionary” : *the filename of the dictionary to be used*, string (default one will be used if parameter not provided)

### API output

Upon successful operation the API will return JSON object with two fields: 
	"nr of entries" : the number of entries matching the search query
	"results" : a list of escaped text strings matching the search query

	In case of error the API will return a JSON object with the following fields: 
		"Code" : the HTTP status code of error			
		"message" : a descriptive message of the possible reasons for the error and a link to these instructions


## Web service design & concurrency

As the core functionality of the service is based on executing an external executable and retrieving its output, I consider the service to be primarily limited in time by IO operations. 
As such the best option to manage concurrency is to use asyncio instead of other options as multithreading.

This drives the choice of the framework to Quart (a asyncio friendly fork of flask). 

Through Quart all requests will be natively managed by coroutines and the only attention point will be to wrap the call to the external executable in a asyncio caller (which is a shell executor running in a separate thread and returning its results when completed).

This choice ensures that requests can be accepted and processed concurrently and results are returned as soon as they are ready.

Quart has two running modes, app.run() is a method for development, whilst in production it runs being served by a ASGI web server (Hypercorn) which is distributed with Quart.

This second mode is the one implemented in the app.

## Termination

My strategy to ensure graceful termination was to override the default signal handler in Quart with a custom one allowing to define a customized set of actions or a specific timeout.

This is done by getting the event loop before starting the app, adding the custom signal handlers, then starting the hypercorn server (which owns the event loop for Quart) passing the event loop modified.

Whilst this technique works, allowing, for example, to add a timeout between the reception of the signal (in my case SIGTERM and SIGINT) and the actual shutdown, or possibly even awaiting all outstanding requests to complete before shutting down, I noticed that the webserver seems to halt the connections immediately.

I spent some time studying the source code of Quart to understand the reason of this behaviour - as i suspected that additional signal handlers might be registered by the app -  but in full honestly I haven’t been able to find a satisfactory solution yet.

This means that at the moment the code will not satisfy the requests still pending when a SIGINT or SIGTERM is received. 

## Testing

A simple tests suite is provided with the code.
Testing is performed via Pytest. 
The module pytest-asyncio allows to test coroutines and a specific fixture is provided by Quart to deploy a test app to which the test client can connect.

I wrote simple test scenarios covering: 
the API endpoints
the web views
the core function

In order to check concurrency vs a blocking call I implemented an undocumented route /wait

which will launch an external process requiring 10 seconds to complete. This allows to check that the server is able to keep serving calls while waiting for the blocking call to be completed.

## Deployment

The app requires python 3.7+ and is deployed under a GIT repository at the following address:

https://github.com/Grifone75/kambi_api

To install it: 
clone the repository in a folder of your choice 
create a virtual environment with the specified requirements.txt 
launch with python kambi_api.py

