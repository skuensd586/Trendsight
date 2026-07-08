import { useEffect, useMemo, useState } from 'react';
import { Bot, SendHorizontal, Sparkles } from 'lucide-react';
import { api, isBackendMode } from '../api/index.js';

const suggestions = ['当前事件为什么升温？', '负面情绪主要来自哪里？', '下一步处置建议是什么？'];

function buildAnswer(event, question) {
  if (!event) return '请选择一个事件后再提问。';
  const normalized = question.trim();
  if (!normalized) return '可以围绕事件起因、风险等级、情绪分布、传播路径或处置建议提问。';
  if (normalized.includes('负面') || normalized.includes('情绪')) {
    return `${event.title} 的负面情绪占比为 ${event.sentiment.negative}%，主要围绕 ${event.keywords
      .slice(0, 3)
      .join('、')} 展开。建议优先查看高传播节点与官方回应后的评论变化。`;
  }
  if (normalized.includes('建议') || normalized.includes('处置')) {
    return `${event.advice} 当前生命周期判断为${event.stage}，风险等级为${event.risk}，应结合热度变化和真实性置信度持续研判。`;
  }
  if (normalized.includes('升温') || normalized.includes('原因') || normalized.includes('为什么')) {
    return `升温原因主要是：${event.cause} 事件随后经由 ${event.pathNodes
      .slice(0, 3)
      .map((node) => node.name)
      .join('、')} 等节点传播，报道量达到 ${event.reportCount.toLocaleString()} 条。`;
  }
  return event.qaSeed;
}

export default function QAPanel({ event, compact = false }) {
  const [question, setQuestion] = useState('');
  const [conversationId, setConversationId] = useState('');
  const [messages, setMessages] = useState(() => [
    {
      role: 'assistant',
      text: event
        ? `已载入「${event.title}」。你可以询问事件起因、风险等级、情绪分布、传播路径或处理建议。`
        : '请选择一个热点事件，我会基于当前看板数据进行分析。',
    },
  ]);

  const eventKey = useMemo(() => event?.id, [event?.id]);

  useEffect(() => {
    setConversationId('');
    setMessages([
      {
        role: 'assistant',
        text: event
          ? `已载入「${event.title}」。你可以询问事件起因、风险等级、情绪分布、传播路径或处理建议。`
          : '请选择一个热点事件，我会基于当前看板数据进行分析。',
      },
    ]);
  }, [eventKey, event]);

  const ask = (value = question) => {
    const text = value.trim();
    if (!text) return;
    setMessages((current) => [...current, { role: 'user', text }]);
    setQuestion('');
    if (isBackendMode()) {
      api
        .askEventQuestion({ eventId: event?.id, conversationId, question: text })
        .then((result) => {
          setConversationId(result.conversation_id || conversationId);
          setMessages((current) => [...current, { role: 'assistant', text: result.answer || '后端暂未返回回答。' }]);
        })
        .catch((error) => {
          setMessages((current) => [...current, { role: 'assistant', text: error.message || '问答接口调用失败。' }]);
        });
      return;
    }
    setMessages((current) => [...current, { role: 'assistant', text: buildAnswer(event, text) }]);
  };

  return (
    <section className={`qa-panel ${compact ? 'compact' : ''}`} key={eventKey}>
      <div className="section-heading">
        <div>
          <span className="eyebrow">Large Model QA</span>
          <h2>智能问答</h2>
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

      <div className="chat-window">
        {messages.map((message, index) => (
          <div className={`chat-message ${message.role}`} key={`${message.role}-${index}`}>
            {message.role === 'assistant' && <Bot size={17} />}
            <p>{message.text}</p>
          </div>
        ))}
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
          placeholder="输入关于当前事件的问题"
        />
        <button type="submit" aria-label="发送问题">
          <SendHorizontal size={18} />
        </button>
      </form>
    </section>
  );
}
