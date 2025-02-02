import os
from azure.identity import DefaultAzureCredential
from azure.identity.aio import ManagedIdentityCredential
from azure.search.documents.indexes.aio import SearchIndexClient
from azure.search.documents.models import VectorizedQuery
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    SearchableField,
)
from azure.search.documents.aio import SearchClient
from azure.identity.aio import ManagedIdentityCredential
import base64

from azure.ai.documentintelligence import DocumentIntelligenceClient
# from azure.ai.documentintelligence.models import AnalyzeResult
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
from quart import current_app

from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

# Create a credential object
credential = DefaultAzureCredential()

indexName = os.getenv("AZURE_SEARCH_INDEX_NAME")

if indexName:
    current_app.logger.info("Using Azure Search index: %s", indexName)
else:
    indexName = "inddd"


try:
    chunkSize = int(os.getenv("AZURE_SEARCH_CHUNK_SIZE", "500").strip())
except ValueError:
    chunkSize = 500
    current_app.logger.warning("Invalid AZURE_SEARCH_CHUNK_SIZE value. Using default: 500")
try:
    Overlap = int(os.getenv("AZURE_SEARCH_CHUNK_SIZE_OVERLAP", "80").strip())
except ValueError:
    Overlap = 80
    current_app.logger.warning("Invalid AZURE_SEARCH_CHUNK_SIZE_OVERLAP value. Using default: 80")

# Set your Azure OpenAI endpoint
azure_openai_endpoint = "https://your-custom-endpoint.openai.azure.com/"

# Create a credential object
credential = DefaultAzureCredential()

# Get the token
token = credential.get_token("https://cognitiveservices.azure.com/.default")


async def retrieve_context(question: str,  bp):
    search_service_url = os.getenv("AZURE_SEARCH_SERVICE_URL")

    if not search_service_url:
        current_app.logger.error("AZURE_SEARCH_SERVICE_URL is not set.")
        raise ValueError("AZURE_SEARCH_SERVICE_URL is not set.")

    current_app.logger.info(f"Using search service URL: {search_service_url}")

    # Convert the question to a vector using OpenAI's embeddings API

    embed_response = await bp.openai_client.embeddings.create(
        input=question,
        model="text-embedding-ada-002"
    )
    question_vector = embed_response.data[0].embedding


    search_client = bp.search_client
    vector_query = VectorizedQuery(
    vector=question_vector,  # Example vector
    k_nearest_neighbors=2,  # Number of results to return
    kind="vector",
    fields="content_vector"
    )

    results = await search_client.search(search_text="*", vector_queries=[vector_query], top=3, 
                                 select=["content"])
    docs = []
    async for result in results:
        docs.append(result["content"])
    return "\n".join(docs)

async def verify_index(search_client):

    index_client = search_client

    index = await index_client.get_index(indexName)
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

# CHANGED: Helper function to chunk text
def chunk_text(text, chunk_size=chunkSize, overlap=Overlap):
    """Split text into chunks of length `chunk_size`, with overlapping of `overlap` chars."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

async def create_or_update_search_index():
    search_service_url = os.getenv("AZURE_SEARCH_SERVICE_URL")

    if not search_service_url:
        current_app.logger.error("AZURE_SEARCH_SERVICE_URL is not set.")
        raise ValueError("AZURE_SEARCH_SERVICE_URL is not set.")

    current_app.logger.info(f"Using search service URL: {search_service_url}")

    index_name = indexName

    # Use ManagedIdentityCredential with the client_id for user-assigned managed identities
    credential = ManagedIdentityCredential(client_id=os.getenv("AZURE_CLIENT_ID"))

    index_client = SearchIndexClient(endpoint=search_service_url, credential=credential)

    # CHANGED: Added fields for filename and chunk_id to store references
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="filename", type=SearchFieldDataType.String),
        SimpleField(name="chunk_id", type=SearchFieldDataType.String),
        SimpleField(name="content", type=SearchFieldDataType.String),
        SearchableField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            dimensions=1536,
            vector_search_configuration="vector-config",
        ),
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
    file_name = file_name.replace(" ", "_")

    if not search_service_url:
        current_app.logger.error("AZURE_SEARCH_SERVICE_URL is not set.")
        raise ValueError("AZURE_SEARCH_SERVICE_URL is not set.")

    current_app.logger.info(f"Using search service URL: {search_service_url}")

    index_name = indexName

    # Use ManagedIdentityCredential with the client_id for user-assigned managed identities
    credential = formrecognizercredential

    search_client = SearchClient(endpoint=search_service_url, index_name=index_name, credential=credential)
    # CHANGED: Chunk the PDF text
    chunks = chunk_text(file_content.replace("\n", " "))
    for i, chunk in enumerate(chunks):
        current_app.logger.error("chunk text:",chunk[:20])
        embed_response = await bp.openai_client.embeddings.create(
            input=chunk,
            model="text-embedding-ada-002"
        )
        embeddings = embed_response.data[0].embedding
        doc_id = f"{file_name.split('.')[0]}chunk{i}"
        document = {
            "id": doc_id,
            "filename": file_name,
            "chunk_id": str(i),
            "content": chunk,
            "content_vector": embeddings
        }
        await search_client.upload_documents(documents=[document])

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

        # Append the SAS token to the blob URL
        blob_url = f"{blob_client.url}?{sas_token}"
        current_app.logger.info(f"Blob URL: {blob_url}")  # Print the blob URL for debugging

        # Extract text from PDF using Form Recognizer
        extracted_text = await extract_text_from_pdf(blob_url, formrecognizercredential)
        current_app.logger.error("extracted text:",extracted_text[:20])
        # Index the PDF content
        await index_pdf_content(file.filename, extracted_text, bp, formrecognizercredential)
        return {"message": "File uploaded successfully", "blob_url": blob_url}, 200
    except Exception as e:
        current_app.logger.error(f"Error uploading file: {e}")
        return {"error": str(e)}, 500



async def extract_text_from_pdf( blob_url, formrecognizercredential):
    form_recognizer_endpoint = os.getenv("FORM_RECOGNIZER_ENDPOINT")
    document_analysis_client = DocumentIntelligenceClient(endpoint=form_recognizer_endpoint, credential=formrecognizercredential)

    poller =  document_analysis_client.begin_analyze_document(
        "prebuilt-invoice", AnalyzeDocumentRequest(url_source=blob_url)
    )
    result =  poller.result()
    extracted_text = ""
    for page in result.pages:
        for line in page.lines:
            extracted_text += line.content + "\n"
    return extracted_text