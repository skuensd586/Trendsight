import { useEffect, useMemo, useState } from 'react';
import AppShell from '../components/AppShell.jsx';
import QAPanel from '../components/QAPanel.jsx';
import { api } from '../api/index.js';
import { events } from '../data/events.js';

export default function QAPage() {
  const [qaEvents, setQaEvents] = useState(events);
  const [eventId, setEventId] = useState(events[0].id);
  const selectedEvent = useMemo(() => qaEvents.find((event) => event.id === eventId) || qaEvents[0], [eventId, qaEvents]);

  useEffect(() => {
    let alive = true;
    api
      .getHotEvents({ sort: 'heat', page: 1, page_size: 20 })
      .then((result) => {
        if (!alive || !result.items?.length) return;
        setQaEvents(result.items);
        setEventId((current) => result.items.some((event) => event.id === current) ? current : result.items[0].id);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  return (
    <AppShell>
      <section className="qa-page-layout">
        <aside className="event-picker">
          <p className="eyebrow">Current Event</p>
          <h1>选择问答事件</h1>
          <p>问答会读取当前事件的热度、情绪、关键词、传播路径和预测状态。</p>
          <div className="picker-list">
            {qaEvents.map((event) => (
              <button
                className={event.id === eventId ? 'active' : ''}
                key={event.id}
                onClick={() => setEventId(event.id)}
                type="button"
              >
                <span>{event.title}</span>
                <b>热度 {event.heat}</b>
              </button>
            ))}
          </div>
        </aside>
        <QAPanel event={selectedEvent} />
      </section>
    </AppShell>
  );
}
