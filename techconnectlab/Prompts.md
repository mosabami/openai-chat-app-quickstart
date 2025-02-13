# start
1.	add a top level comment to this file
1.	help me add function comments to each function
1. @workspace Document this project. Include an overview and sections for dependencies, features, requirements, constraints, summary. Format the documentation as markdown and show the raw markdown file contents
1.	add a top level comment to this file
1. /explain 
1. /doc
1.	how should i use the verify_index function in my #file:rag.py in my #file:chat.py file?
1.	@workspace /explain  what the functions in this file does


# Add a new feature
1. @workspace  take a  look at the code in the src folder. my app allows uploading pdf documents to azure storage, and using form recognizer to extract text and uses azure openai to convert the text to embeddings which are then stored in azure search. user clicks the upload button when a file is attached to trigger this. however user doesnt get any feedback that these actions are processing after they click the button or if they need to click it again. can you make it so that the interface shows a rolling animation that indicates that the file is being uploaded, disables the upload button, etc until the actions are completed and the successfully uploaded document alert is presented?

1. @workspace take a look at the code in the src folder. my app allows uploading pdf documents to azure storage, and using form recognizer to extract text and uses azure openai to convert the text to embeddings which are then stored in azure search. user clicks the upload button when a file is attached to trigger this. however user doesnt get any feedback that these actions are processing after they click the button or if they need to click it again. can you make it so that the interface shows a rolling animationon the upload button that indicates that the file is being uploaded, disables the upload button, etc until the actions are completed and the successfully uploaded document alert is presented? make sure that the password verification logic isnt impacted by this change. let me know which part of the code to change as opposed to sending the entire file updated

    do i need a css file to define the "spinner-border", etc classes?
    can you give me what the entire new index.html file will look like with these changes?

# Code quality

@workspace i have a lot of script code in my index.html file. given this is a python quantapp, is it possible for me to move all my script logic outside my index.html file?

*select retrieve_context function and enter* @workspace /explain How can I improve the readability of the [selected code]? perhaps extract some functionalities into their own functions?
    i dont want to change bp because it means blueprint. 
given the _generate_sas_url function you created for me earlier, is there anywhere else in my #file:rag.py that function can be used?

awesome. can you give me the updated code for process_pdf_upload function?



*select the process_pdf_upload function and enter* @workspace /explain #selection How can I improve the maintainability of the [selected code]?


@workspace /explain What are some options for simplifying the [selected code]?

# Performance
*select the create_or_update_search_index* function and ask @workspace /explain How can I improve exception handling the [selected code]?
     do i need to update the #file:requirements.txt file for the newly imported azure.core.exceptions package?
     *show the monitoring*

*select the process_pdf_upload* function and ask Prompt: @workspace /explain How can I reduce unexpected issues for the [selected code]?

*select the process_pdf_upload* function and ask Prompt: @workspace /explain How can I improve unit test support for the [selected code]? 

what other part of my code do i need to update for the new version of the process_pdf_upload function to work properly?

@workspace /explain How can I implement proper authentication in the #selection function using a azure b2c authentication service? right now my code just requests a password when they try to upload document. how does that code change? how do users "log in"? i need all the code i need to authenticate to my b2c tenant using microsoft login page. i want most of auth functionality to be in a separate file auth.py

how do i figure out what my AZURE_B2C_CLIENT_ID, AZURE_B2C_CLIENT_SECRET, AZURE_B2C_AUTHORITY are from the azure portal?

<!-- @workspace ok in this case how does the user authenticate? right now my code just requests a password when they try to upload document. how does that code change? how do users "log in"?

ok and how do i add users that should be able to upload documents to the app on the azure side if i dont want to add a registration page? -->


@workspace my process_pdf_upload function currently uploads the pdf and also adds the index to azure search. this means my users have to wait for files to be uploaded before they can continue using the app. i want to change this so that a unction app takes care of the index_pdf_content part of the function. how do i create the function app using the same managed identity my other services are using (sharedidentity) and has the index_pdf_content logic? i want my function to be triggered by any upload to my blob storage.

