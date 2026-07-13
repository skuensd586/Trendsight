import { useEffect, useMemo, useRef, useState } from 'react';
import { Bot, LoaderCircle, SendHorizontal, Sparkles } from 'lucide-react';
import { api, isBackendMode } from '../api/index.js';

const suggestions = ['这件事为什么升温？', '负面情绪主要来自哪里？', '下一步建议怎么做？'];
const markdownDividerPattern = /^(?:-{3,}|\*{3,}|_{3,})$/;
const markdownHeadingPattern = /^(#{1,6})(?:\s+(.*?)\s*#*|\s*)$/;

function normalizeMarkdownText(text) {
  return String(text || '')
    .replace(/\r\n?/g, '\n')
    .replace(/([^\n])\s+(\*\*\s*\d+[.)、]?)/g, '$1\n$2')
    .replace(/([^\n])\s+(#{1,6}\s*)/g, '$1\n$2')
    .replace(/([^\n])\s+((?:-{3,}|\*{3,}|_{3,})\s*)/g, '$1\n$2')
    .replace(/([^\n])\s+(\d+[.)、]\s+)/g, '$1\n$2')
    .replace(/([^\n])\s+([-*•]\s+)/g, '$1\n$2')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function renderInlineMarkdown(text, keyPrefix) {
  return String(text)
    .split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
    .filter(Boolean)
    .map((part, index) => {
      const key = `${keyPrefix}-${index}`;
      if (part.startsWith('**') && part.endsWith('**')) {
        const value = part.slice(2, -2).trim();
        return value ? <strong key={key}>{value}</strong> : null;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={key}>{part.slice(1, -1)}</code>;
      }
      return <span key={key}>{part}</span>;
    });
}

function renderMessageContent(text) {
  const lines = normalizeMarkdownText(text).split('\n');
  const blocks = [];
  let paragraph = [];
  let list = null;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const value = paragraph.join(' ');
    blocks.push({
      type: 'paragraph',
      value,
    });
    paragraph = [];
  };

  const flushList = () => {
    if (!list) return;
    blocks.push(list);
    list = null;
  };

  const pushDivider = () => {
    if (!blocks.length || blocks[blocks.length - 1].type === 'divider') return;
    blocks.push({ type: 'divider' });
  };

  const parseListLine = (trimmed) => {
    const emphasizedOrderedHeading = trimmed.match(/^\*\*\s*(\d+)[.)、]\s*([^*]+?)\*\*\s*(.*)$/);
    if (emphasizedOrderedHeading) {
      const title = emphasizedOrderedHeading[2].trim();
      const rest = emphasizedOrderedHeading[3].trim();
      return { type: 'ordered-list', value: `**${title}** ${rest}`.trim() };
    }

    const emphasizedOrdered = trimmed.match(/^\*\*\s*(\d+)[.)、]?\s*\*\*\s*(.*)$/);
    if (emphasizedOrdered) return { type: 'ordered-list', value: emphasizedOrdered[2].replace(/\s+\*\*$/, '').trim() };

    const ordered = trimmed.match(/^(\d+)[.)、]\s+(.*)$/);
    if (ordered) return { type: 'ordered-list', value: ordered[2] };

    const unordered = trimmed.match(/^[-*•]\s+(.*)$/);
    if (unordered) return { type: 'unordered-list', value: unordered[1] };

    return null;
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    if (markdownDividerPattern.test(trimmed)) {
      flushParagraph();
      flushList();
      pushDivider();
      return;
    }

    const heading = trimmed.match(markdownHeadingPattern);
    if (heading) {
      const value = (heading[2] || '').trim();
      flushParagraph();
      flushList();
      if (value) blocks.push({ type: 'heading', value });
      return;
    }

    const listItem = parseListLine(trimmed);

    if (listItem) {
      flushParagraph();
      if (!list || list.type !== listItem.type) {
        flushList();
        list = { type: listItem.type, items: [] };
      }
      list.items.push(listItem.value);
      return;
    }

    flushList();
    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();

  if (blocks[blocks.length - 1]?.type === 'divider') blocks.pop();

  if (!blocks.length) return null;

  return blocks.map((block, index) => {
    if (block.type === 'paragraph') {
      return <p key={`paragraph-${index}`}>{renderInlineMarkdown(block.value, `paragraph-${index}`)}</p>;
    }
    if (block.type === 'ordered-list') {
      return (
        <ol key={`ordered-${index}`}>
          {block.items.map((item, itemIndex) => (
            <li key={`ordered-${index}-${itemIndex}`}>{renderInlineMarkdown(item, `ordered-${index}-${itemIndex}`)}</li>
          ))}
        </ol>
      );
    }
    if (block.type === 'heading') {
      return (
        <h3 className="message-heading" key={`heading-${index}`}>
          {renderInlineMarkdown(block.value, `heading-${index}`)}
        </h3>
      );
    }
    if (block.type === 'divider') {
      return <hr className="message-divider" key={`divider-${index}`} />;
    }
    if (block.type === 'unordered-list') {
      return (
        <ul key={`unordered-${index}`}>
          {block.items.map((item, itemIndex) => (
            <li key={`unordered-${index}-${itemIndex}`}>{renderInlineMarkdown(item, `unordered-${index}-${itemIndex}`)}</li>
          ))}
        </ul>
      );
    }
    return null;
  });
}

function buildAnswer(event, question) {
  if (!event) return '请选择一个事件后再提问。';
  const normalized = question.trim();
  if (!normalized) return '请提问事件起因、风险等级、情绪分布、传播路径或处置建议。';
  if (normalized.includes('负面') || normalized.includes('情绪')) {
    return `${event.title} 的负面情绪占比为 ${event.sentiment.negative}%，主要围绕 ${event.keywords
      .slice(0, 3)
      .join('、')} 集中。建议先查看高传播节点，以及官方回应后的评论变化。`;
  }
  if (normalized.includes('建议') || normalized.includes('处置')) {
    return `${event.advice} 当前处于${event.stage}，风险等级为${event.risk}。请同时关注热度变化和可信度。`;
  }
  if (normalized.includes('升温') || normalized.includes('原因') || normalized.includes('为什么')) {
    return `主要原因：${event.cause}。之后经由 ${event.pathNodes
      .slice(0, 3)
      .map((node) => node.name)
      .join('、')} 等节点传播，报道量达到 ${event.reportCount.toLocaleString()} 条。`;
  }
  return event.qaSeed;
}

export default function QAPanel({ event, compact = false }) {
  const chatWindowRef = useRef(null);
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [isAnswering, setIsAnswering] = useState(false);
  const [messages, setMessages] = useState(() => [
    {
      role: 'assistant',
      text: event
        ? `已载入「${event.title}」。可询问起因、风险、情绪、传播路径和处置建议。`
        : '先选择一个事件，再开始问答。',
    },
  ]);

  const eventKey = useMemo(() => event?.id, [event?.id]);

  useEffect(() => {
    setConversationId('');
    setIsAnswering(false);
    setMessages([
      {
        role: 'assistant',
        text: event
          ? `已载入「${event.title}」。可询问起因、风险、情绪、传播路径和处置建议。`
          : '先选择一个事件，再开始问答。',
      },
    ]);
  }, [eventKey, event]);

  useEffect(() => {
    const chatWindow = chatWindowRef.current;
    if (!chatWindow) return;
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }, [eventKey, messages, isAnswering]);

  const ask = (value = question) => {
    const text = value.trim();
    if (!text || isAnswering) return;
    setMessages((current) => [...current, { role: 'user', text }]);
    setQuestion('');
    setIsAnswering(true);
    if (isBackendMode()) {
      api
        .askEventQuestion({ eventId: event?.id, conversationId, question: text })
        .then((result) => {
          setConversationId(result.conversation_id || conversationId);
          setMessages((current) => [...current, { role: 'assistant', text: result.answer || '数据服务没有返回回答。' }]);
        })
        .catch((error) => {
          setMessages((current) => [...current, { role: 'assistant', text: error.message || '问答请求失败，请稍后重试。' }]);
        })
        .finally(() => {
          setIsAnswering(false);
        });
      return;
    }
    window.setTimeout(() => {
      setMessages((current) => [...current, { role: 'assistant', text: buildAnswer(event, text) }]);
      setIsAnswering(false);
    }, 520);
  };

  return (
    <section className={`qa-panel ${compact ? 'compact' : ''}`} key={eventKey}>
      <div className="section-heading">
        <div>
          <h2>事件问答</h2>
        </div>
        <Sparkles size={20} />
      </div>

      <div className="suggestion-row">
        {suggestions.map((item) => (
          <button key={item} type="button" onClick={() => ask(item)}>
            {item}
          </button>
        ))}
      </div>

      <div className="chat-window" ref={chatWindowRef}>
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.role === 'assistant' && <Bot size={17} />}
            <div className="message-content">{renderMessageContent(message.text)}</div>
          </div>
        ))}
        {isAnswering && (
          <div className="chat-message assistant is-loading" aria-live="polite">
            <Bot size={17} />
            <div className="message-content qa-loading-message">
              <LoaderCircle className="qa-loading-spinner" size={18} />
              <span>正在整理回答</span>
            </div>
          </div>
        )}
      </div>

      <form
        className="qa-input"
        onSubmit={(eventSubmit) => {
          eventSubmit.preventDefault();
          ask();
        }}
      >
        <input
          value={question}
          onChange={(eventChange) => setQuestion(eventChange.target.value)}
          placeholder="输入你想问的问题"
        />
        <button type="submit" aria-label="发送问题">
          <SendHorizontal size={18} />
        </button>
      </form>
    </section>
  );
}
