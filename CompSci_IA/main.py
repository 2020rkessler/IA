from __future__ import print_function

import json
import pickle
import os.path

from googleapiclient.discovery import build, BatchHttpRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from flask import Flask, request, render_template

app = Flask(__name__)

emails = {}

def get_emails_count():
    return sum(len(value) for value in emails.values())

def categorize_email(request_id, response, exception):

    subject = ''
    sender = ''
    sender_name = ''
    sender_email = ''

    response_headers = response['messages'][0]['payload']['headers']

    for header in response_headers:
        if header['name'] == 'Subject':
            subject = header['value']
        elif header['name'] == 'From':
            sender = header['value']

    #sender info is returned as:- 'Sender Name <sender@service.com>' if sender has a name beginning with letters, otherwise the email address is returned
    #to extract the email we use the split function on '<'

    if sender.find('<') != -1:
        sender = sender.split('<')
        #remove any whitespace using the strip function and remove the quotation marks around sender name (if present)
        sender_name = sender[0].strip().replace('"', '')
        #remove the remaining '>'
        sender_email = sender[1].replace('>', '')

    #if sender doesn't have a name then only the email is returned (i.e. test@gmail.com)
    else:
        sender_email = sender

    email = {
        'sender_name': sender_name,
        'sender_email': sender_email,
        'subject': subject
    }

    #Now, categorize the email

    #username of sender. For example username 'john12@gmail.com' -> 'john12'
    username = sender_email.split('@')[0]

    #split the sender name on empty space to get first and last name inside the list
    sender_name_list = sender_name.split(' ')

    #check to see if the email is from a student:
    if username[:4] == '2020':
        emails['grade12'].append(email)

    elif username[:4] == '2021':
        emails['grade11'].append(email)

    elif username[:4] == '2022':
        emails['grade10'].append(email)

    elif username[:4] == '2023':
        emails['grade9'].append(email)

    #check to see if the email is from a teacher
    #if the split on empty space was completeld successfuly, (for example, 'Andrew Lodespoto' will satisfy the if but 'AmazonTest' will not)
    elif len(sender_name_list) > 1:

        first_name = sender_name_list[0]
        last_name = sender_name_list[1]

        expected_teacher_username = first_name[0].lower() + last_name.lower()

        if expected_teacher_username == username:
            emails['teachers'].append(email)

        else:
            emails['other'].append(email)

    #if the email doesn't fit into any of the categories, add the emails to the category named "other"
    else:
        emails['other'].append(email)

@app.route("/")
def index():

    #using global here so that changes made to emails object effect it out of the scope of this function
    global emails
    next_page_token = ''

    #if user is requesting more emails by clicking the "load more" button then, in that case, don't want to reinitialize the existing emails object -- Instead, append the new mails inside them inside the existing lists
    if request.args.get('token'):
        next_page_token = request.args.get('token')

    #user is requesting emails from the first batch. In this case we need to intialize the emails object
    else:
        emails = {
            'grade9': [],
            'grade10': [],
            'grade11': [],
            'grade12': [],
            'teachers': [],
            'other': []
        }

    #If modifying these scopes, delete the file token.pickle.
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    creds = None

    #The file token.pickle stores the user's access and refresh tokens, and is created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    #If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        #Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)

    #Call the Gmail API to get list of theads based on the page token
    results = service.users().threads().list(
        userId='me', q='-from:me', pageToken=next_page_token).execute()

    #nextPageToken is returned when there are some remaining emails which weren't fetched in the original request
    if 'nextPageToken' in results:
        next_page_token = results['nextPageToken']
    else:
        next_page_token = ''

    #get threads object from the results
    threads = results.get('threads', [])
    #extract id for each thread and add to thread_ids list
    thread_ids = [thread['id'] for thread in threads]

    #intitalize a batch request to fetch all email threads info against the thread ids
    batch_request = BatchHttpRequest()

    #iterate over each thread id
    for thread_id in thread_ids:

        #add the current thread id fetch request to the batch request. We are requesting the From and Subject headers from the API.
        #Callback is the function that runs for each response of the batch request.
        batch_request.add(service.users().threads().get(userId='me',
                                                        id=thread_id,
                                                        format='metadata',
                                                        metadataHeaders=['From', 'Subject']),
                          callback=categorize_email)

    #execute the batch request to fetch the emails
    batch_request.execute()

    emails_counts = get_emails_count()

    return render_template('index.html', emails=emails, next_page_token=next_page_token, emails_count=emails_counts)

@app.errorhandler(Exception)
def exception_handler(error):
    return render_template('error.html')

app.run()
