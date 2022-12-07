import json
import boto3
import mailparser

from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

sagemaker_client = boto3.client('sagemaker-runtime')
s3_client = boto3.client('s3')

region = 'us-east-1' 
S3_BUCKET = '6998hw3emails'

def lambda_handler(event, context):
    # TODO implement
    object_key = event['Records'][0]['s3']['object']['key']

    file_content = s3_client.get_object(
        Bucket=S3_BUCKET, Key=object_key)["Body"].read()
        
    mail = mailparser.parse_from_bytes(file_content)
    
    date = str(mail.date)[0:10]
    subject = mail.subject

    test_messages = mail.text_plain
    test_messages = ' '.join(test_messages)
    test_messages = test_messages.strip()
    test_messages = test_messages.replace('\n',' ').replace('\r', ' ')
    
    messages = []
    messages.append(test_messages)
    
    vocabulary_length = 9013
    one_hot_test_messages = one_hot_encode(messages, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    message = json.dumps(encoded_test_messages.tolist())
    response = sagemaker_client.invoke_endpoint(
        EndpointName='sms-spam-classifier-mxnet-2022-11-20-01-29-21-634',
        Body=message,
        ContentType = 'text/csv'
    )
    
    response_body = response['Body']
    string_body = response_body.next().decode()
    prediction_arr = string_body.replace('[','').split()
    
    print(prediction_arr)

    classifications = ['not spam', 'spam']
    
    if int(prediction_arr[3][0]) == 0:
        confidence = 100 - round(float(prediction_arr[1][0:5]) * 100, 3)
    else:
        confidence = round(float(prediction_arr[1][0:5]) * 100, 3)
    
    SENDER = "Spam Detection <emilyl2009@gmail.com>"

    RECIPIENT = str(mail.from_[0][1])

    AWS_REGION = region

    SUBJECT = "Spam Detection"

    BODY_TEXT = """We received your email sent at {EMAIL_RECEIVE_DATE} with the subject '{EMAIL_SUBJECT}'.""".format(EMAIL_RECEIVE_DATE = date, EMAIL_SUBJECT = subject)
    SAMPLE = """Here is a 240 character sample of the email body:{EMAIL_BODY}""".format(EMAIL_BODY = test_messages[0:241])
    CATEGORY = """The email was categorized as {CLASSIFICATION} with a {CLASSIFICATION_CONFIDENCE_SCORE}% confidence.""".format(CLASSIFICATION_CONFIDENCE_SCORE = confidence, CLASSIFICATION = classifications[int(prediction_arr[3][0])])
    
    BODY_HTML = f"""\
    <html>
    <head></head>
    <body>
    <h1>Hello!</h1>
    <p>{BODY_TEXT}</p>
    <p>{SAMPLE}</p>
    <p>{CATEGORY}</p>
    </body>
    </html>
"""

    CHARSET = "utf-8"

    client = boto3.client('ses',region_name=region)

    msg = MIMEMultipart('mixed')
    
    msg['Subject'] = SUBJECT 
    msg['From'] = SENDER 
    msg['To'] = RECIPIENT

    msg_body = MIMEMultipart('alternative')

    textpart = MIMEText(BODY_TEXT.encode(CHARSET), 'plain', CHARSET)
    htmlpart = MIMEText(BODY_HTML.encode(CHARSET), 'html', CHARSET)

    msg_body.attach(textpart)
    msg_body.attach(htmlpart)

    msg.attach(msg_body)

    try:
#Provide the contents of the email.
        response = client.send_raw_email(
            Source=SENDER,
            Destinations=[
                RECIPIENT
            ],
            RawMessage={
                'Data':msg.as_string(),
            }
        )
# Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

    #return {
    #    'statusCode': 200,
    #    'body': json.dumps('Hello from Lambda!')
    #}