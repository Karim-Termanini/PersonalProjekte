<?php
$name = $_post['name'];
$visitor_email = $_post['email'];
$subject = $_post['subject'];
$message = $_post['message'];

$email_from = 'info@RAADO.com'

$email_subject ='New From Submission'

$email_body ="User Name:$name.\n".
              "User Email:$visitor_email.\n".
              "User Subject:$subject.\n".
               "User Message:$message.\n";
$to = 'termaninikarim@gmail.com';

$headers ="From:$email_from\r\n";

$headers .="Reply-to:$visitor_email\r\n";

mail($to,$email_subject,$email_body,$headers);

header("Location:contact.html");
?>