function Message({ role, content }) {
    const renderContent = (text) => {
      const urlPattern = /(https?:\/\/[^\s)]+)/g;
      const parts = text.split(urlPattern);
  
      return parts.map((part, index) => {
        if (urlPattern.test(part)) {
          return (
            <a
              key={index}
              href={part}
              target="_blank"
              rel="noreferrer"
            >
              {part}
            </a>
          );
        }
  
        return part;
      });
    };
  
    return (
      <div className={`message ${role}`}>
        <strong>
          {role === "user" ? "You" : "Assistant"}
        </strong>
  
        <p>{renderContent(content)}</p>
      </div>
    );
  }
  
  export default Message;