import json
import os

from azure.identity.aio import (
    AzureDeveloperCliCredential,
    ChainedTokenCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)

from azure.identity import ManagedIdentityCredential as SyncManIdent
from openai import AsyncAzureOpenAI
from azure.storage.blob.aio import BlobServiceClient
from azure.search.documents.aio import SearchClient
from quart import (
    Blueprint,
    Response,
    current_app,
    render_template,
    request,
    stream_with_context,
)

from quartapp.rag import create_or_update_search_index, process_pdf_upload, retrieve_context

import time

rate_limit_counter = {
    "count": 0,
    "start": time.time()
}

rate_limit = 120
rate_limit_response_message = "Sorry i have reached my rate limit, try again in an hour"

bp = Blueprint("chat", __name__, template_folder="templates", static_folder="static")

indexName = os.getenv("AZURE_SEARCH_INDEX_NAME")

if indexName:
    current_app.logger.info("Using Azure Search index: %s", indexName)
else:
    indexName = "inddd"

fileUploadPassword = os.getenv("FILE_UPLOAD_PASSWORD")
if fileUploadPassword:
    current_app.logger.info("Using fileUploadPassword: %s", fileUploadPassword)
else:
    fileUploadPassword = "P@ssword"

def return_good_delta(delta):
    text = "\n" + delta
    return {"delta": {"content": text, "function_call": None, "refusal": None, "role": None, "tool_calls": None}, 
                         "finish_reason": None, "index": 0, "logprobs": None, 
                         "content_filter_results": {"hate": {"filtered": False, "severity": "safe"}, "self_harm": {"filtered": False, "severity": "safe"}, 
                            "sexual": {"filtered": False, "severity": "safe"}, "violence": {"filtered": False, "severity": "safe"}}}

@bp.before_app_serving
async def configure_openai():
    # Use ManagedIdentityCredential with the client_id for user-assigned managed identities
    user_assigned_managed_identity_credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))

    # Use AzureDeveloperCliCredential with the current tenant.
    azure_dev_cli_credential = AzureDeveloperCliCredential(tenant_id=os.getenv("AZURE_TENANT_ID"), process_timeout=60)

    # Create a ChainedTokenCredential with ManagedIdentityCredential and AzureDeveloperCliCredential
    azure_credential = ChainedTokenCredential(user_assigned_managed_identity_credential, azure_dev_cli_credential)
    current_app.logger.info("Using Azure OpenAI with credential")

    # Get the token provider for Azure OpenAI based on the selected Azure credential
    token_provider = get_bearer_token_provider(azure_credential, "https://cognitiveservices.azure.com/.default")
    if not os.getenv("AZURE_OPENAI_ENDPOINT"):
        raise ValueError("AZURE_OPENAI_ENDPOINT is required for Azure OpenAI")
    if not os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"):
        raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT is required for Azure OpenAI")

    # Create the Asynchronous Azure OpenAI client
    bp.openai_client = AsyncAzureOpenAI(
        api_version=os.getenv("AZURE_OPENAI_API_VERSION") or "2024-02-15-preview",
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_ad_token_provider=token_provider,
    )
    # Set the model name to the Azure OpenAI model deployment name
    bp.openai_model = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")

    # Configure Azure Blob Storage client
    storage_account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL")
    if storage_account_url:
        bp.blob_service_client = BlobServiceClient(
            account_url=storage_account_url,
            credential=azure_credential
        )
    else:
        bp.blob_service_client = None
        current_app.logger.warning("AZURE_STORAGE_ACCOUNT_URL is not set. File uploads will be disabled.")

    # Configure Azure Search client
    search_service_url = os.getenv("AZURE_SEARCH_SERVICE_URL")
    if search_service_url:
        bp.search_client = SearchClient(
            endpoint=search_service_url,
            index_name=indexName,
            credential=azure_credential
        )
    else:
        bp.search_client = None
        current_app.logger.warning("AZURE_SEARCH_SERVICE_URL is not set. Search functionality will be disabled.")

    # Create or update the search index
    try:
        await create_or_update_search_index()
    except Exception as e:
        current_app.logger.error(f"Error creating or updating search index: {e}")

@bp.after_app_serving
async def shutdown_openai():
    await bp.openai_client.close()
    if bp.blob_service_client:
        await bp.blob_service_client.close()
    if bp.search_client:
        await bp.search_client.close()

@bp.get("/")
async def index():
    return await render_template("index.html")


# @bp.post("/chat")
# async def chat():
#     azuresearchcredential = SyncManIdent(client_id=os.getenv("AZURE_CLIENT_ID"))
#     request_messages = (await request.get_json())["messages"]
#     user_question = request_messages[-1]["content"]

#     # Retrieve context from Azure Search
#     # return Response(json.dumps(user_question), status=200)
#     retrieved_data = await retrieve_context(user_question,  bp)
#     context = "\n".join([item.get("content", "") for item in retrieved_data if item.get("content")])
#     references = [ ]
#     doc_copy = [ ]
#     for item in retrieved_data:
#         if item.get("filename"):
#             filename = item.get("filename")
#             if filename in doc_copy:
#                 continue
#             doc_copy.append(filename)
#             doc_url = item.get("doc_url")
#             reference = f"[{filename}]({doc_url})"
#             references.append(reference)
#     if references:
#         references_text = f"**References:**\n" + "\n".join(references)
#         return Response(json.dumps(references_text), status=200)
#     else:
#         return Response(json.dumps({"error": "I'm sorry, I can only answer questions related to the topics this app was built for."}), status=400)
    
#     return Response(json.dumps(context), status=200)

@bp.post("/chat/stream")
async def chat_handler():
    global rate_limit_counter
    current = time.time()
    if current - rate_limit_counter["start"] > 3600:
        # Reset after an hour
        rate_limit_counter = {"count": 0, "start": current}
    if rate_limit_counter["count"] > rate_limit:
        @stream_with_context
        async def ratelimit_response_stream():
            yield json.dumps(return_good_delta(rate_limit_response_message), ensure_ascii=False) + "\n"
        return Response(ratelimit_response_stream())

        # return Response( json.dumps(return_good_delta(rate_limit_response_message), ensure_ascii=False) , status=429)
    rate_limit_counter["count"] += 1

    request_messages = (await request.get_json())["messages"]
    user_question = request_messages[-1]["content"]
    azuresearchcredential = SyncManIdent(client_id=os.getenv("AZURE_CLIENT_ID"))
    # Retrieve context from Azure Search
    retrieved_data = await retrieve_context(user_question, bp)
    context = "\n".join([item.get("content", "") for item in retrieved_data if item.get("content")])
    references = [ ]
    doc_copy = [ ]
    for item in retrieved_data:
        if item.get("filename"):
            filename = item.get("filename")
            if filename in doc_copy:
                continue
            doc_copy.append(filename)
            doc_url = item.get("doc_url")
            reference = f"[{filename}]({doc_url})"
            references.append(reference)

    if not context:
        return Response(json.dumps({"error": "I'm sorry, I can only answer questions related to the topics this app was built for."}), status=400)
    # return Response(json.dumps(retrieved_data), status=200) 

    @stream_with_context
    async def response_stream():
        all_messages = [
            {"role": "system", "content": "Use the context below to answer the user's question."},
            {"role": "user", "content": f"Context: {context}\n\nQuestion: {user_question}"}
        ]

        chat_coroutine = bp.openai_client.chat.completions.create(
            model=bp.openai_model,
            messages=all_messages,
            stream=True,
        )
        try:
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict["choices"]:
                    yield json.dumps(event_dict["choices"][0], ensure_ascii=False) + "\n"
            if references:
                references_text = f"\n**References:**\n" + "\n".join(references)
                # yield json.dumps(return_good_delta("\n"), ensure_ascii=False) 
                yield json.dumps(return_good_delta(references_text), ensure_ascii=False) + "\n"

        except Exception as e:
            current_app.logger.error(e)
            yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"
        # Append references at the end of the response


    return Response(response_stream())

@bp.post("/upload")
async def upload_file():
    if not bp.blob_service_client:
        current_app.logger.error("File upload is disabled. Missing Azure Storage account configuration.")
        return {"error": "File upload is disabled. Missing Azure Storage account configuration."}, 500

    files = await request.files
    form_data = await request.form
    if "file" not in files or "password" not in form_data:
        current_app.logger.error("No file part or password in the request.")
        return {"error": "No file part or password"}, 400

    file = files["file"]
    password = form_data["password"]
    if file.filename == "":
        current_app.logger.error("No selected file.")
        return {"error": "No selected file"}, 400
    
    if password != fileUploadPassword:
        current_app.logger.error("Invalid password.")
        return {"error": "Invalid password"}, 403

    try:
        formrecognizercredential = SyncManIdent(client_id=os.getenv("AZURE_CLIENT_ID"))
        result =  await process_pdf_upload(file, bp, formrecognizercredential)
        # result =  process_pdf_upload(file, bp)
        return result
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}")
        return {"error": str(e)}, 500