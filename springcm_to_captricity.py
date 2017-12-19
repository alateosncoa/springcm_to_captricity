import json
import requests
import datetime
import sys
import pysftp
import paramiko
import os
import shutil
import io
import csv
from slackclient import SlackClient
from suds.client import Client


# the API token for captricity
API_TOKEN = 'fb03fafb3bb14b98ad61cde92aac284a' 

# the REST headers to authenticate with the captricity service
HEADERS = {
	'Accept':'application/json',
	'User-Agent':'Captricity13-App',
	'Captricity-API-Token':API_TOKEN
}

# find a file given its name (denoted by "str")
def findFile(str):
	print(str)
	# download the designated file
	sftp.get(str)
	f.write(str + " was downloaded successfully \n")
	slackIt(str + " was downloaded successfully")
	# delete the file from the remote host
	sftp.unlink(str)
	f.write(str + " was removed from springcm's ftp \n")
	slackIt(str + " was removed from springcm's ftp")
	# replace the full path file name with just the file name
	str = str.replace("SCSEP Portal/Outbound/","")
	# move the file name to the pdfs directory that temporarily holds the downloaded pdf files
	shutil.move(os.path.dirname(os.path.realpath(__file__))+"\\"+str,pdfs_directory+str)
	to_captricity.append(pdfs_directory+str)
	f.write(str + " was moved to the local temporary pdfs directory \n")
	slackIt(str + " was moved to the local temporary pdfs directory")

# callback function that gets called once on every directory. not currently in use so we just use "pass" to proceed
def listDirectory(str):
	pass

# callback function that gets invoke on error, in which case it will output a short message	
def doSomething(str):
	print(str + " is a weird type of file")
	f.write(str + " is a weird type of file")
	slackIt("@channel " + str + " is a weird type of file")

# uses the GET method to send a request given a set of headers. returns the response as json encoded	
def get_method(url, headers=HEADERS):
    output = requests.get(url, headers=headers)
    return json.loads(output.text)

# uses the POST method to send a request given a set of headers. returns the response as json encoded
def post_method(url, payload=None, files=None, headers=HEADERS):
    if files:
        output = requests.post(url, data=payload, files=files, headers=headers)
    else:
        output = requests.post(url, data=payload, headers=headers)
    return json.loads(output.text)
	
# utlitily method for outputting messages to Slack
def slackIt(msg):
    #connect to the ncoa-team Slack channel to send debug messages to the #scsep_doc_mover channel
    slack_client = SlackClient('xoxp-51134241895-51226051829-113549076167-2068d1387159c75e83f58d02899711c7')
    slack_client.api_call("chat.postMessage",channel="scsep_doc_mover",text=msg)

# the timestamp that will be used as part of the batch's name when sent to captricity
batch_timestamp = 'SCSEP-SCM ' + str(datetime.datetime.today().strftime('%Y-%m-%d %I%p'))

# the base url for the captricity service
BASE_URL = 'shreddr.captricity.com'
	
# name of log file
log_file = "results.txt"

# name of batch ids file
batch_ids_file = "batch_ids.txt"

# batch ids to process
batch_ids = []
	
# if the log file already exists then remove it
if os.path.isfile(log_file):
	os.remove(log_file)
	
# open a log file to store results
f = io.open(log_file,"w")

# open the batch file ids file in read mode
h = io.open(batch_ids_file,"r")

# load batch ids
for batch_id in h:
	batch_ids.append(batch_id.replace("\n",""))

# close batch ids file for reading	
h.close()

# create csv files for all outstanding jobs
for batch_id in batch_ids:
	CSV_URL = "https://"+BASE_URL+"/api/v1/job/"+str(batch_id)+"/csv/"
	try:
		response = requests.get(CSV_URL,headers=HEADERS)
		if str(response.content).find('File is unavailable') == -1:
			with open(os.path.join("csvs", str(batch_id)+".csv"), 'wb') as j:
				j.write(response.content)
				for batch_id_ in batch_ids:
					if batch_id_ == batch_id:
						batch_ids.remove(batch_id)
				j.close()
	except Exception as e:
		print(e)
		pass

# contains the paths of the files to be uploaded to captricity
# each path is a concatenation of the local temp pdf directory, and the file name that was downloaded from springcm
to_captricity = []

# the path to the directory that will temporarily hold the downloaded pdfs from springcm
pdfs_directory = os.path.dirname(os.path.realpath(__file__)) + "\\pdfs\\"

# options object that contains different parameters for the sftp connection to springcm
cnopts = pysftp.CnOpts()

# we will not be using any host keys for the sftp connection to springcm
cnopts.hostkeys = None

# connection object to springcm
sftp = pysftp.Connection('sftpna21.springcm.com', username='daniel.dennis@ncoa.org', password='Kj19u!4q2bcLahOOZsm9',cnopts=cnopts)
f.write("Connected to springcm \n")
slackIt("Connected to springcm \n")

# recursively walk through the "SCSEP Portal/Outbound/" folder and apply 3 callback functions
sftp.walktree('SCSEP Portal/Outbound/',findFile,listDirectory,doSomething)

# change working directory in springcm to ready for csv file uploads
with sftp.cd('SCSEP Portal/Inbound/'):
	# iterate through the csvs folder and upload all the csv files to springcm
	for root, dirs, filenames in os.walk('csvs/'):
		for file in filenames:
			try:
				sftp.put('csvs/'+file)
				os.remove('csvs/'+file)
			except:
				f.write("Something went wrong when uploading the csv files to captricity and/or when removing them from the temp folder".upper() + " \n")
				slackIt("Something went wrong when uploading the csv files to captricity and/or when removing them from the temp folder".upper() + " \n")
	
# close sftp connection to springcm	
sftp.close()
f.write("Closed connection with springcm \n")
slackIt("Closed connection with springcm \n")

# open the batch file ids file
g = io.open(batch_ids_file,"w")

# if no outbound springcm files were found exit this application
if len(to_captricity) == 0:
	print("\n")
	print("No files were found in outbound directory. Quitting app".upper())
	f.write("No files were found in outbound directory. Quitting app".upper() + " \n")
	slackIt("No files were found in outbound directory. Quitting app".upper() + " \n")
	f.close()
	for batch_id in batch_ids:
		g.write(batch_id + "\n")
		g.close()
	sys.exit()

# create a new empty batch to hold files
new_batch_details = {
    'name': batch_timestamp,
    'sorting_enabled': True,
    'is_sorting_only': False,
    'documents': [122347]  # this is where you need to put the template ID's required
}

for batch_id in batch_ids:
	g.write(batch_id + "\n")

# create a new batch for captricity
new_batch = post_method(url='https://{}/api/v1/batch/'.format(BASE_URL), 
                        payload=new_batch_details,
                        headers=HEADERS)		
			
# log in the python console the captricity metadata given on the recently submitted batch
print('')
print('Batch ID:  {}'.format(new_batch['id']))
print('Batch name:  {}'.format(new_batch['name']))
print('Batch created:  {}'.format(new_batch['created']))
print('Batch status:  {}'.format(new_batch['status']))
print('')

f.write(' \n')
f.write('Batch ID:  {}'.format(new_batch['id']) + "\n")
f.write('Batch name:  {}'.format(new_batch['name'])+ "\n")
f.write('Batch created:  {}'.format(new_batch['created'])+ "\n")
f.write('Batch status:  {}'.format(new_batch['status'])+ "\n")
f.write(' \n')

slackIt(' \n')
slackIt('Batch ID:  {}'.format(new_batch['id']) + "\n")
slackIt('Batch name:  {}'.format(new_batch['name'])+ "\n")
slackIt('Batch created:  {}'.format(new_batch['created'])+ "\n")
slackIt('Batch status:  {}'.format(new_batch['status'])+ "\n")
slackIt(' \n')

# now that the batch is open, upload all of the files as part of this batch to captricity
for to_upload in to_captricity:
	file_payload = {
		'uploaded_with': 'api'	
	}
	
	with open(to_upload, 'rb') as fo:
	
		f.write("Opened connection to captricity \n")
		slackIt("Opened connection to captricity \n")
		
		file_details = {'uploaded_file': fo }
		f.write("File details: " + str(file_details) + " \n")
		slackIt("File details: " + str(file_details) + " \n")
		
		upload_file = post_method(url='https://{}/api/v1/batch/{}/batch-file/'.format(BASE_URL, new_batch['id']),
							   payload=file_payload,
							   files=file_details,
							   headers=HEADERS)
							   
		f.write("File uploaded successfully \n")
		slackIt("File uploaded successfully \n")
		
		f.write("This connection to captricity is closed \n")
		slackIt("This connection to captricity is closed \n")

# once all the desired files are uploaded, submit the batch
submit_batch = post_method(url='https://{}/api/v1/batch/{}/submit'.format(BASE_URL, new_batch['id']),
                           headers=HEADERS)

						   
# if the batch was accepted, then remove the pertinent files from the temporary pdf directory
if not submit_batch['is_reject_batch']:
	# add batch id to batch ids file						
	g.write(str(submit_batch['related_job_id']) + "\n")	
	f.write("The batch was successfully submitted to and acknowledged by captricity \n")
	slackIt("The batch was successfully submitted to and acknowledged by captricity \n")
	for to_delete in to_captricity:
		try:
			os.remove(to_delete)
			f.write(str(to_delete) + " was removed from the local temp folder \n")
			slackIt(str(to_delete) + " was removed from the local temp folder \n")
		except Exception as e:
			fe = open('error.txt', 'a')
			#slackIt("Something went wrong when trying to delete " + str(to_delete))
			#slackIt(e)
			fe.write(e)
			fe.write('\n')
			print(e)
			pass
if submit_batch['is_reject_batch']:
	f.write("Error from captricity \n")
	f.write(submit_batch)
	slackIt("Error from captricity \n")
	slackIt(submit_batch)
		
f.close()
g.close()