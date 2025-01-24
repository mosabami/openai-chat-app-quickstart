import os
import openai
from azure.identity import DefaultAzureCredential
import asyncio
from azure.identity.aio import ManagedIdentityCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    SearchableField,
)
from azure.search.documents.aio import SearchClient
from azure.ai.formrecognizer.aio import DocumentAnalysisClient
from azure.identity.aio import ManagedIdentityCredential

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from quart import current_app

from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

# Create a credential object
credential = DefaultAzureCredential()



# Set your Azure OpenAI endpoint
azure_openai_endpoint = "https://your-custom-endpoint.openai.azure.com/"

# Create a credential object
credential = DefaultAzureCredential()

# Get the token
token = credential.get_token("https://cognitiveservices.azure.com/.default")

# Instantiate the OpenAI client
# textembedingclient = openai.OpenAI(api_key=token.token, api_base='https://wojh5fksuhjjs-cog.openai.azure.com/', api_version= '2024-02-15-preview')

async def verify_index(search_client):

    index_client = search_client

    index = await index_client.get_index("pdf-index")
    info = {}
    for field in index.fields:
        if field.name == "content_vector":
            # print("Field name:", field.name)
            info["Field name"] = field.name
            # print("Type:", field.type)
            info["Type"] = field.type
            # print("Dimensions:", getattr(field, "dimensions", None))
            info["Dimensions"] = getattr(field, "dimensions", None)
        break
    return info

async def create_or_update_search_index():
    search_service_url = os.getenv("AZURE_SEARCH_SERVICE_URL")

    if not search_service_url:
        current_app.logger.error("AZURE_SEARCH_SERVICE_URL is not set.")
        raise ValueError("AZURE_SEARCH_SERVICE_URL is not set.")

    current_app.logger.info(f"Using search service URL: {search_service_url}")

    index_name = "pdf-index"

    # Use ManagedIdentityCredential with the client_id for user-assigned managed identities
    credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))

    index_client = SearchIndexClient(endpoint=search_service_url, credential=credential)

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="content", type=SearchFieldDataType.String),
        SearchableField(name="content_vector", type=SearchFieldDataType.Collection(SearchFieldDataType.Single), dimensions=1536, vector_search_configuration="vector-config")
    ]

    vector_search = VectorSearch(
        algorithm_configurations=[
            VectorSearchAlgorithmConfiguration(
                name="vector-config",
                kind="hnsw"
            )
        ]
    )

    index = SearchIndex(name=index_name, fields=fields, vector_search=vector_search)

    try:
        await index_client.create_index(index)
        current_app.logger.info(f"Index '{index_name}' created successfully.")
    except Exception as e:
        if "ResourceNameAlreadyInUse" in str(e):
            current_app.logger.info(f"Index '{index_name}' already exists. Updating index.")
            await index_client.create_or_update_index(index)
        else:
            current_app.logger.error(f"Error creating or updating index: {e}")
            raise

async def index_pdf_content(file_name, file_content, bp, formrecognizercredential):
    search_service_url = os.getenv("AZURE_SEARCH_SERVICE_URL")

    if not search_service_url:
        current_app.logger.error("AZURE_SEARCH_SERVICE_URL is not set.")
        raise ValueError("AZURE_SEARCH_SERVICE_URL is not set.")

    current_app.logger.info(f"Using search service URL: {search_service_url}")

    index_name = "pdf-indexx"

    # Use ManagedIdentityCredential with the client_id for user-assigned managed identities
    credential = formrecognizercredential

    search_client = SearchClient(endpoint=search_service_url, index_name=index_name, credential=credential)
    text = file_content.replace("\n", " ")
    # return text
    response = await bp.openai_client.embeddings.create(input=text, model="text-embedding-ada-002")
    # return type(response)
    embeddings = response.data[0].embedding
    # return embeddings
    # req_info = info = await verify_index(search_client)
    # req_info = {}
    # req_info["embeddings length"] = len(embeddings)
    # return req_info
    document = {
        "id": file_name.split(".")[0],
        "content": file_content,
        "content_vector": embeddings
    }

    await search_client.upload_documents(documents=[document])



#     async with document_analysis_client:
#         poller = await document_analysis_client.begin_analyze_document("prebuilt-document", AnalyzeDocumentRequest(url_source=blob_url ))
#         result = await poller.result()

#     extracted_text = ""
#     for page in result.pages:
#         for line in page.lines:
#             extracted_text += line.content + "\n"

#     return extracted_text


async def process_pdf_upload(file, bp, formrecognizercredential):
    blob_service_client = bp.blob_service_client
    container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")
    account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

    try:
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=file.filename)
        await blob_client.upload_blob(file.stream, overwrite=True)
        # Generate a SAS token for the blob
        sas_token = generate_blob_sas(
            account_name=blob_client.account_name,
            container_name=container_name,
            blob_name=file.filename,
            account_key=account_key,
            permission=BlobSasPermissions(read=True, write=True, delete=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )

        # blob_url = 'https://wojh5fksuhjjsx.blob.core.windows.net/pdf-uploads/lafit.pdf?sp=r&st=2025-01-24T00:02:40Z&se=2025-01-24T08:02:40Z&spr=https&sv=2022-11-02&sr=b&sig=GOB%2Fkx5kAeyHd%2BWEiJkwMAjTnnKJH2H7GTDt1oBRGTw%3D'
        # Append the SAS token to the blob URL
        blob_url = f"{blob_client.url}?{sas_token}"
        current_app.logger.info(f"Blob URL: {blob_url}")  # Print the blob URL for debugging

        # Extract text from PDF using Form Recognizer
        extracted_text = await extract_text_from_pdf(blob_url, formrecognizercredential)

        # Index the PDF content
        await index_pdf_content(file.filename, extracted_text, bp, formrecognizercredential)
        return {"message": "File uploaded successfully", "blob_url": blob_url}, 200
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}")
        return {"error": str(e)}, 500
    

# async def process_pdf_upload(file, bp, formrecognizercredential):
#     blob_service_client = bp.blob_service_client
#     container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME")

#     try:
#         blob_client = blob_service_client.get_blob_client(container=container_name, blob=file.filename)
#         await blob_client.upload_blob(file.stream, overwrite=True)

#         # Get the URL of the uploaded blob
#         blob_url = 'https://wojh5fksuhjjsx.blob.core.windows.net/pdf-uploads/lafi.pdf?sp=r&st=2025-01-24T08:11:31Z&se=2025-01-26T16:11:31Z&sv=2022-11-02&sr=b&sig=jOKHOmFm%2BSzdVvOetFfYs7VwZROtTrmShB1hIewIlU8%3D'
#         # blob_url = blob_client.url
#         current_app.logger.info(f"Blob URL: {blob_url}")  # Print the blob URL for debugging

#         # Extract text from PDF using Form Recognizer
#         extracted_text =  await extract_text_from_pdf( blob_url, formrecognizercredential)

#         # Index the PDF content
#         res = await index_pdf_content(file_name = file.filename, file_content=extracted_text, bp = bp, formrecognizercredential=formrecognizercredential)

#         # Return the URL of the uploaded blob
#         return {"message": "File uploaded successfully", "blob_url": res}, 200
#     except Exception as e:
#         current_app.logger.error(f"Error uploading file: {e}")
#         return {"error": str(e)}, 500



async def extract_text_from_pdf( blob_url, formrecognizercredential):
    # sample document
    
    form_recognizer_endpoint = os.getenv("FORM_RECOGNIZER_ENDPOINT")
    # document_intelligence_client = DocumentIntelligenceClient(endpoint=form_recognizer_endpoint, credential=credentials)

    credential = formrecognizercredential
    document_analysis_client = DocumentIntelligenceClient(endpoint=form_recognizer_endpoint, credential=credential)

    poller =  document_analysis_client.begin_analyze_document(
        "prebuilt-invoice", AnalyzeDocumentRequest(url_source=blob_url)
    )
    result =  poller.result()
    extracted_text = ""
    for page in result.pages:
        for line in page.lines:
            extracted_text += line.content + "\n"
    return extracted_text


# def analyze_invoice(credentials):
#     # sample document
#     invoice_url = "https://raw.githubusercontent.com/Azure-Samples/cognitive-services-REST-api-samples/master/curl/form-recognizer/sample-invoice.pdf"
    
#     form_recognizer_endpoint = os.getenv("FORM_RECOGNIZER_ENDPOINT")
#     document_intelligence_client = DocumentIntelligenceClient(endpoint=form_recognizer_endpoint, credential=credentials)

#     poller = document_intelligence_client.begin_analyze_document(
#         "prebuilt-invoice", AnalyzeDocumentRequest(url_source=invoice_url)
#     )
#     result = poller.result()
#     extracted_text = ""
#     for page in result.pages:
#         for line in page.lines:
#             extracted_text += line.content + "\n"
#     return extracted_text