import json
import requests
import datetime
import sys
import pysftp
import paramiko
import os
import shutil

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
	# delete the file from the remote host
	sftp.unlink(str)
	# replace the full path file name with just the file name
	str = str.replace("SCSEP Portal/Outbound/","")
	# move the file name to the pdfs directory that temporarily holds the downloaded pdf files
	shutil.move(os.path.dirname(os.path.realpath(__file__))+"\\"+str,pdfs_directory+str)
	to_captricity.append(pdfs_directory+str)

# callback function that gets called once on every directory. not currently in use so we just use "pass" to proceed
def listDirectory(str):
	pass

# callback function that gets invoke on error, in which case it will output a short message	
def doSomething(str):
	print(str + " is a weird type of file")

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
sftp = pysftp.Connection('sftpna21.springcm.com', username='ddennis+ncoa', password='Kj19u!4q2bcLahOOZsm8',cnopts=cnopts)

# recursively walk through the "SCSEP Portal/Outbound/" folder and apply 3 callback functions
sftp.walktree('SCSEP Portal/Outbound/',findFile,listDirectory,doSomething)

# close sftp connection to springcm	
sftp.close()

# if no outbound springcm files were found exit this application
if len(to_captricity) == 0:
	print("\n")
	print("No files were found in outbound directory. Quitting app".upper())
	sys.exit()

# the timestamp that will be used as part of the batch's name when sent to captricity
batch_timestamp = 'SCSEP-SCM ' + str(datetime.datetime.today().strftime('%Y-%m-%d %I%p'))

# the base url for the captricity service
BASE_URL = 'shreddr.captricity.com'

# create a new empty batch to hold files
new_batch_details = {
    'name': batch_timestamp,
    'sorting_enabled': True,
    'is_sorting_only': False,
    'documents': [122347]  # this is where you need to put the template ID's required
}

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

# now that the batch is open, upload all of the files as part of this batch to captricity
for to_upload in to_captricity:
	file_payload = {
		'uploaded_with': 'api'	
	}
	
	fo = open(to_upload, 'rb')
	
	file_details = {'uploaded_file': fo }
	
	upload_file = post_method(url='https://{}/api/v1/batch/{}/batch-file/'.format(BASE_URL, new_batch['id']),
						   payload=file_payload,
						   files=file_details,
						   headers=HEADERS)
						   
	fo.close()

# once all the desired files are uploaded, submit the batch
submit_batch = post_method(url='https://{}/api/v1/batch/{}/submit'.format(BASE_URL, new_batch['id']),
                           headers=HEADERS)

# if the batch was accepted, then remove the pertinent files from the temporary pdf directory
if not submit_batch['is_reject_batch']:						   
	for to_delete in to_captricity:
		os.remove(to_delete)