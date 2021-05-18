from quart import Quart, request, render_template
from hypercorn.asyncio import serve
from hypercorn.config import Config
import asyncio
import logging
from logging import Formatter
import time
import signal
from quart.logging import serving_handler


#this global mutable object is just a simple way to send a flag to all views when shutting down 
global_flags = {"shutting_down":False};

#setting up logging
logging.getLogger('quart.serving').setLevel(logging.INFO)
logging.getLogger('quart.app').setLevel(logging.INFO)
logging.basicConfig(level=logging.DEBUG,filename="my_api.log",format="%(asctime)s - %(name)s - %(levelname)s - %(message)s - [in %(pathname)s:%(lineno)d]")

#default library path and file for the text to be searched
LIBRARY_PATH = 'library/'
DEFAULT_LIBRARY = 'quote_file.txt'

#default timeout for custom shutdown
TIMEOUT = 15


app = Quart(__name__)

#this allows to handle all http errors with a single decorator in the handling function
# -- https://stackoverflow.com/questions/27760113/how-can-i-implement-a-custom-error-handler-for-all-http-errors-in-flask
app.config['TRAP_HTTP_EXCEPTIONS']=True


#this is a support function to simulate a blocking call. Calls a bash script which waits and then return some data
async def wait_function():
	#add an attribute to signal request
	asyncio.current_task().outstanding = True
	await asyncio.sleep(10)
	proc = await asyncio.create_subprocess_shell('./blocking_command.sh',
		stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE) #Note this is to prevent subprocess to receive a SIGINT 
	print(proc)
	stdout, stderr = await proc.communicate()
	print(stdout.decode('utf-8'))
	return stdout.decode('utf-8')
	#return 'DONE'

#main core function, wrapper around the linux executable we're going to call to serve the requests
async def core_function_grep(**kwargs):

	#parameters are retrieved and converted here
	search_term = kwargs.get('search')
	dictionary = kwargs.get('dictionary',DEFAULT_LIBRARY)
	nresults = kwargs.get('nresults')
	n_aft = str(kwargs.get('n_after',0))
	n_bef = str(kwargs.get('n_before',0))

	#we launch grep assembling the required parameters
	shell_command = 'grep '+' -r '+' -A '+n_aft+' -B '+n_bef+' --group-separator="___" '+'"'+search_term+'"'+' '+LIBRARY_PATH+dictionary
	proc = await asyncio.create_subprocess_shell(
			shell_command,
		stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.PIPE) #Note this is to prevent subprocess to receive a SIGINT see https://stackoverflow.com/questions/13593223/making-sure-a-python-script-with-subprocesses-dies-on-sigint

	stdout, stderr = await proc.communicate()
		
	if proc.returncode == 0:
		results = stdout.decode('utf-8').split('___')
		status = 200
		#return only nresult items. If nresults = None, slicing will return the full list
		return results[:nresults],status 
	
	else:
		results = stderr.decode('utf-8')[5:] #strippping "grep" from error message and leaving useful information
		status = 403
		return results,status

#this can be used to log some detailed information at every request but at the moment I won't use it
@app.before_request
async def log_request_info():
    #logging.getLogger('quart.app').info('Headers: %s', request.headers)
    pass


#generic HTTP error handler with customised messages
@app.errorhandler(Exception) 
async def handle_http_error(e): 
	custom_messages = {
		404:"The URL specified is not correct, please refer to /api/v1/web for instructions",
		500:"Internal server error",
		501:"Not implemented, please refer to /api/v1/web for instructions",
	}
	message = custom_messages.get(e.code,"Arghh! There was an error! Please refer to /api/v1/web for instructions")

	logging.getLogger('quart.app').error('status '+str(e.code)+' - message: '+message + ' - headers: ' + str(request.headers))
	return {'Code' : e.code, 'message' : message},e.code


## ----- ROUTES -------------------------------------------------------

@app.route('/')
async def hello():
	return 'Hello'


@app.route('/wait')
async def wait():
	if not(global_flags['shutting_down']):
		asyncio.current_task().set_name("FG - wait")
		#add an attribute to signal request
		asyncio.current_task().outstanding = True
		message = await wait_function()
		return message
	else:
		return "shutting down",404		

#route to show instruction page
@app.route('/api/v1/web')
async def api_v1_info():
	return await render_template('api_v1.html')

#route for the json api
@app.route('/api/v1/json', methods=['POST'])
async def api_json():

	if not(global_flags['shutting_down']):

		parameters = {}
		api_syntax_error = False
		request_data = await request.get_json(force=True)
		
		action = request_data['action']
		if action == 'all': 
			parameters['search'] = '$'
			parameters['nresults'] = None


		if action == 'search':

			if request_data.get('term'):
				parameters['search'] = str(request_data['term'])
				#optional parameters
				parameters['dictionary'] = request_data.get('dictionary',DEFAULT_LIBRARY)
				parameters['nresults'] = request_data.get('nresults',None)
				parameters['n_before'] = request_data.get('n_before',0)
				parameters['n_after'] = request_data.get('n_after',0)

			else:
				api_syntax_error = True

		if api_syntax_error:
			message = "API keys not recognized"
			status = 400
		else: 
			message, status = await core_function_grep(**parameters)


		if status >=400:
			logging.getLogger('quart.app').error('status '+str(status)+' - message: '+message + ' - headers: ' + str(request.headers))

		return {"nr of entries":len(message),"results":message},status
	
	else:

		return {'Code' : 503, 'message' : "Server shutting down..."},503


#route for the json api with wrong methods (i only put GET at the moment)
@app.route('/api/v1/json', methods=['GET'])
async def api_json_wrong_methods():
	return {'Code':405, 'message':'Method not allowed for this API, please refer to /api/v1/web for instructions'},405


# ------ END ROUTES ------------------------------------



# definition of events and handler for a graceful shutdown
shutdown_event = asyncio.Event()

async def ask_exit(signame):
	
	logging.getLogger('quart.app').info("received signal {}: initiating shutdown in {}...".format(signame,TIMEOUT))
	global_flags['shutting_down'] = True #switches routes to denial message
	await asyncio.sleep(TIMEOUT)
	logging.getLogger('quart.app').info("...shutting down")
	shutdown_event.set()


#main function

if __name__ == "__main__":

	#basic hypercorn config
	config = Config()
	config.from_mapping({
		"graceful_timeout":30,
		})


	#adding custom signal handlers for interrupts to the event loop
	loop = asyncio.get_event_loop()

	for signame in ('SIGINT', 'SIGTERM'):
		loop.add_signal_handler(
			getattr(signal, signame), 
			lambda: asyncio.create_task(ask_exit(signame))
			)

	#run the loop with indication for shutdown trigger (see hypercorn docs at https://pgjones.gitlab.io/hypercorn/how_to_guides/api_usage.html)
	loop.run_until_complete(
		serve(app, config, shutdown_trigger=shutdown_event.wait),
	)

