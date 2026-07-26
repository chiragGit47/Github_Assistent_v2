import { useState } from "react";

import Message from "./Message";
import FileUpload from "./FileUpload";
import api from "../services/api";


function ChatBox({ sessionId }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      content: "How can I help with your GitHub account?",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [preparedUpload, setPreparedUpload] =
    useState(null);

  const clearPreparedUpload = () => {
    setPreparedUpload(null);
  };

  const sendMessage = async () => {
    const visibleMessage = input.trim();

    if (!visibleMessage || loading) {
      return;
    }

    let backendMessage = visibleMessage;

    if (preparedUpload) {
      backendMessage +=
        "\n\nPrepared file details:" +
        `\nupload_id: ${preparedUpload.uploadId}` +
        `\nfilename: ${preparedUpload.filename}` +
        `\nfile_type: ${
          preparedUpload.isZip
            ? "zip"
            : "single_file"
        }`;
    }

    setMessages((currentMessages) => [
      ...currentMessages,
      {
        role: "user",
        content: visibleMessage,
      },
    ]);

    setInput("");
    setLoading(true);

    try {
      const response = await api.post("/chat", {
        session_id: sessionId,
        message: backendMessage,
      });

      const responseData = response.data;

      console.log("CHAT RESPONSE:", responseData);

      let assistantMessage =
        responseData.message ||
        "Request completed.";

      if (
        responseData.action === "upload_single_file" ||
        responseData.action === "upload_project_zip"
      ) {
        const resultUrl =
          responseData.data?.commit_url ||
          responseData.data?.file?.url;

        if (resultUrl) {
          assistantMessage +=
            `\n\nRepository: ${
              responseData.data?.repository || "Unknown"
            }` +
            `\nBranch: ${
              responseData.data?.branch || "main"
            }` +
            `\nUploaded files: ${
              responseData.data?.uploaded_count || 1
            }` +
            `\nView result: ${resultUrl}`;
        }
      }

      if (
        responseData.success === false &&
        responseData.error
      ) {
        assistantMessage +=
          `\n\nError: ${responseData.error}`;
      }

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: assistantMessage,
        },
      ]);

      const uploadActions = [
        "upload_single_file",
        "upload_project_zip",
      ];

      const uploadExpired =
        responseData.error?.toLowerCase().includes(
          "expired"
        ) ||
        responseData.message?.toLowerCase().includes(
          "expired"
        ) ||
        responseData.data?.error
          ?.toLowerCase()
          .includes("expired");

      if (
        uploadActions.includes(responseData.action) &&
        (responseData.success || uploadExpired)
      ) {
        clearPreparedUpload();
      }
    } catch (error) {
      console.error("CHAT ERROR:", error);

      const responseData = error.response?.data;

      const errorMessage =
        responseData?.error ||
        responseData?.message ||
        responseData?.detail ||
        error.message ||
        "Something went wrong.";

      setMessages((currentMessages) => [
        ...currentMessages,
        {
          role: "assistant",
          content: errorMessage,
        },
      ]);

      const expiredError =
        String(errorMessage)
          .toLowerCase()
          .includes("expired") ||
        String(errorMessage)
          .toLowerCase()
          .includes("not found");

      if (expiredError) {
        clearPreparedUpload();
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage();
  };

  return (
    <section className="chat-box">
      <FileUpload
        key={
          preparedUpload?.uploadId ||
          "empty-upload"
        }
        sessionId={sessionId}
        onPrepared={setPreparedUpload}
      />

      {preparedUpload && (
        <div className="prepared-upload">
          <div>
            <p>
              Ready: {preparedUpload.filename}
            </p>

            <small>
              Type:{" "}
              {preparedUpload.isZip
                ? "ZIP project"
                : "Single file"}
            </small>
          </div>

          <button
            type="button"
            onClick={clearPreparedUpload}
          >
            Remove
          </button>
        </div>
      )}

        <div className="messages">
        {messages.map((message, index) => (
            <Message
            key={`${message.role}-${index}`}
            role={message.role}
            content={message.content}
            action={message.action}
            data={message.data}
            />
        ))}

        {loading && (
            <Message
            role="assistant"
            content={
                preparedUpload
                ? "Uploading your file..."
                : "Processing your request..."
            }
            />
        )}
        </div>

      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          placeholder={
            preparedUpload
              ? "Tell me which repository to upload this file to"
              : "Ask me about your GitHub repositories"
          }
          onChange={(event) =>
            setInput(event.target.value)
          }
        />

        <button
          type="submit"
          disabled={
            loading ||
            !input.trim()
          }
        >
          Send
        </button>
      </form>
    </section>
  );
}

export default ChatBox;