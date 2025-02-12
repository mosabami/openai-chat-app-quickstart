document.addEventListener("DOMContentLoaded", () => {
  const maxMessages = 10; // Maximum number of messages to keep
  const form = document.getElementById("chat-form");
  const messageInput = document.getElementById("message");
  const targetContainer = document.getElementById("messages");
  const userTemplate = document.querySelector("#message-template-user");
  const assistantTemplate = document.querySelector("#message-template-assistant");
  const converter = new showdown.Converter();
  const messages = [];
  const client = new ChatProtocol.AIChatProtocolClient("/chat");

  // Chat form submission event
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = messageInput.value;

    // Append user's message
    const userTemplateClone = userTemplate.content.cloneNode(true);
    userTemplateClone.querySelector(".message-content").innerText = message;
    targetContainer.appendChild(userTemplateClone);

    // Append assistant's message placeholder
    const assistantTemplateClone = assistantTemplate.content.cloneNode(true);
    let messageDiv = assistantTemplateClone.querySelector(".message-content");
    targetContainer.appendChild(assistantTemplateClone);

    // Add user's message to messages array
    messages.push({ role: "user", content: message });
    // Keep only the last maxMessages messages
    if (messages.length > maxMessages) {
      messages.splice(0, messages.length - maxMessages);
    }

    try {
      const result = await client.getStreamedCompletion(messages);
      let answer = "";
      for await (const response of result) {
        if (!response.delta) continue;
        if (response.delta.content) {
          // Clear div if it's the first answer chunk we receive
          if (answer === "") {
            messageDiv.innerHTML = "";
          }
          answer += response.delta.content;
          messageDiv.innerHTML = converter.makeHtml(answer);
          messageDiv.scrollIntoView();
        }
        if (response.error) {
          messageDiv.innerHTML = "Error: " + response.error;
        }
      }
      messages.push({ role: "assistant", content: answer });
      if (messages.length > maxMessages) {
        messages.splice(0, messages.length - maxMessages);
      }
      messageInput.value = "";
    } catch (error) {
      messageDiv.innerHTML = "Error: " + error;
    }
  });

  // Drag and drop functionality for file upload
  const dropZone = document.getElementById("drop-zone");
  const fileInput = document.getElementById("file-input");
  const uploadFileButton = document.getElementById("upload-file-button");

  dropZone.addEventListener("click", () => fileInput.click());
  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("border-primary");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("border-primary"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("border-primary");
    fileInput.files = e.dataTransfer.files;
    updateDropZoneText(fileInput.files[0].name);
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      updateDropZoneText(fileInput.files[0].name);
    }
  });
  function updateDropZoneText(fileName) {
    dropZone.innerText = `Selected file: ${fileName}`;
  }

  // File upload functionality with spinner and disabled button
  uploadFileButton.addEventListener("click", async () => {
    const file = fileInput.files[0];
    const password = document.getElementById("upload-password").value;
    if (!file) {
      alert("Please select a file first.");
      return;
    }
    if (!password) {
      alert("Please enter a password.");
      return;
    }
    // Disable button and show spinner
    uploadFileButton.disabled = true;
    document.getElementById("upload-text").textContent = "Uploading...";
    document.getElementById("upload-spinner").style.display = "inline-block";

    const formData = new FormData();
    formData.append("file", file);
    formData.append("password", password);

    try {
      const response = await fetch("/upload", {
        method: "POST",
        body: formData
      });
      if (response.ok) {
        alert("File uploaded successfully!");
      } else {
        const errorData = await response.json();
        alert("Failed to upload file: " + errorData.error);
      }
    } catch (error) {
      alert("Error: " + error);
    } finally {
      // Re-enable button and hide spinner
      uploadFileButton.disabled = false;
      document.getElementById("upload-text").textContent = "Upload";
      document.getElementById("upload-spinner").style.display = "none";
    }
  });
});