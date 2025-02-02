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

from quartapp.rag import create_or_update_search_index, process_pdf_upload

bp = Blueprint("chat", __name__, template_folder="templates", static_folder="static")

indexName = os.getenv("AZURE_SEARCH_INDEX_NAME")

if indexName:
    current_app.logger.info("Using Azure Search index: %s", indexName)
else:
    indexName = "inddd"

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

@bp.post("/chat/stream")
async def chat_handler():
    request_messages = (await request.get_json())["messages"]

    @stream_with_context
    async def response_stream():
        # This sends all messages, so API request may exceed token limits
        all_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
        ] + request_messages

        chat_coroutine = bp.openai_client.chat.completions.create(
            # Azure Open AI takes the deployment name as the model name
            model=bp.openai_model,
            messages=all_messages,
            stream=True,
        )
        try:
            async for event in await chat_coroutine:
                event_dict = event.model_dump()
                if event_dict["choices"]:
                    yield json.dumps(event_dict["choices"][0], ensure_ascii=False) + "\n"
        except Exception as e:
            current_app.logger.error(e)
            yield json.dumps({"error": str(e)}, ensure_ascii=False) + "\n"

    return Response(response_stream())

@bp.post("/upload")
async def upload_file():
    if not bp.blob_service_client:
        current_app.logger.error("File upload is disabled. Missing Azure Storage account configuration.")
        return {"error": "File upload is disabled. Missing Azure Storage account configuration."}, 500

    files = await request.files
    if "file" not in files:
        current_app.logger.error("No file part in the request.")
        return {"error": "No file part"}, 400

    file = files["file"]
    if file.filename == "":
        current_app.logger.error("No selected file.")
        return {"error": "No selected file"}, 400

    try:
        formrecognizercredential = SyncManIdent(client_id=os.getenv("AZURE_CLIENT_ID"))
        result =  await process_pdf_upload(file, bp, formrecognizercredential)
        # result =  process_pdf_upload(file, bp)
        return result
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}")
        return {"error": str(e)}, 500