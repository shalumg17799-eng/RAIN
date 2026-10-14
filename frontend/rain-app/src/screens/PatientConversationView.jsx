import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HeartPulse, CalendarCheck, Video, Bus, Pill, Bot } from 'lucide-react';
import MobilePhoneFrame from '../components/layout/MobilePhoneFrame';
import ChatInput from '../components/chat/ChatInput';

const NAVY = '#003366';
const PATIENT = { name: 'Elena', firstName: 'Elena' };

// Scripted, plain-language patient flow (mock). No provider intelligence — the
// patient only ever sees their own appointments, visits, rides, and refills.
const FLOWS = {
  greeting: {
    ai: "Hi Elena! 👋 I'm your RAIN care assistant. You have a prenatal check-up coming up, and I can help you join by video, get a ride, or refill your prescription. What would you like to do?",
    chips: ['When is my next appointment?', 'Can I see the doctor by video this week?', 'How do I get a ride to my appointment?', 'I need to refill my medication'],
  },
  appointment: {
    ai: "Your next prenatal check-up is on Tuesday, July 7 at 10:00 AM with your care team. The nearest clinic is a long drive from you, so you can join by video instead, or I can arrange a ride. Which would you prefer?",
    chips: ['Set up a video visit', 'Get me a ride', 'I need to refill my medication'],
  },
  video: {
    ai: "Great choice! 📱 You can see your doctor by video this Thursday at 2:00 PM — right from your phone, with no travel needed. I've saved a spot for you. Want me to confirm it?",
    chips: ['Yes, confirm my video visit', "Actually, I'd rather get a ride"],
  },
  confirm_video: {
    ai: "✅ All set! Your video visit is booked for Thursday at 2:00 PM. You'll get a text with a link to join, and a reminder an hour before. Is there anything else I can help with?",
    chips: ['How do I get a ride to my appointment?', 'I need to refill my medication'],
  },
  ride: {
    ai: "I can arrange a ride for you. 🚐 A medical transport van can pick you up at home and bring you to your July 7 appointment and back — at no cost to you. Want me to schedule it?",
    chips: ['Yes, schedule my ride', 'Set up a video visit instead'],
  },
  confirm_ride: {
    ai: "✅ Your ride is scheduled! The van will pick you up Tuesday, July 7 at 8:30 AM. The driver will call when they're on the way. You're all set — anything else?",
    chips: ['Can I see the doctor by video this week?', 'I need to refill my medication'],
  },
  refill: {
    ai: "I can help with that. 💊 Your prenatal vitamins are ready to refill. I can send the request to your pharmacy in Winnemucca, or have them delivered to your home. Which works best?",
    chips: ['Deliver them to my home', "I'll pick them up"],
  },
  deliver_refill: {
    ai: "✅ Done! Your prenatal vitamins will be delivered to your home in 2–3 days, and we'll text you when they ship. Take care, Elena! 💙",
    chips: ['When is my next appointment?', 'How do I get a ride to my appointment?'],
  },
  pickup_refill: {
    ai: "✅ Done! Your prenatal vitamins will be ready for pickup at your Winnemucca pharmacy tomorrow after 12:00 PM. We'll text you when they're ready. Anything else?",
    chips: ['When is my next appointment?', 'Can I see the doctor by video this week?'],
  },
  fallback: {
    ai: "I'm here to help with your appointments, video visits, rides, and prescriptions. You can tap one of the options below, or just tell me what you need. 💙",
    chips: ['When is my next appointment?', 'Can I see the doctor by video this week?', 'How do I get a ride to my appointment?', 'I need to refill my medication'],
  },
};

const CHIP_TO_KEY = {
  'When is my next appointment?': 'appointment',
  'Can I see the doctor by video this week?': 'video',
  'How do I get a ride to my appointment?': 'ride',
  'I need to refill my medication': 'refill',
  'Set up a video visit': 'video',
  'Set up a video visit instead': 'video',
  'Get me a ride': 'ride',
  'Yes, confirm my video visit': 'confirm_video',
  "Actually, I'd rather get a ride": 'ride',
  'Yes, schedule my ride': 'confirm_ride',
  'Deliver them to my home': 'deliver_refill',
  "I'll pick them up": 'pickup_refill',
};

function resolveKey(text) {
  if (CHIP_TO_KEY[text]) return CHIP_TO_KEY[text];
  const t = text.toLowerCase();
  if (/(appointment|check[- ]?up|visit time|when)/.test(t)) return 'appointment';
  if (/(video|virtual|telehealth|online)/.test(t)) return 'video';
  if (/(ride|transport|drive|pick.?up|get there)/.test(t)) return 'ride';
  if (/(refill|medication|prescription|vitamin|pharmacy|medicine)/.test(t)) return 'refill';
  return 'fallback';
}

const reminders = [
  { icon: CalendarCheck, tint: 'bg-blue-50 text-blue-600', title: 'Prenatal check-up', detail: 'Tue, Jul 7 · 10:00 AM', chip: 'When is my next appointment?' },
  { icon: Video, tint: 'bg-emerald-50 text-emerald-600', title: 'Video visit available', detail: 'See your doctor this week', chip: 'Can I see the doctor by video this week?' },
  { icon: Bus, tint: 'bg-violet-50 text-violet-600', title: 'Need a ride?', detail: 'Free medical transport to your visit', chip: 'How do I get a ride to my appointment?' },
  { icon: Pill, tint: 'bg-amber-50 text-amber-600', title: 'Prenatal vitamins', detail: 'Ready to refill', chip: 'I need to refill my medication' },
];

function Bubble({ role, text }) {
  const isUser = role === 'user';
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}
      className={`flex items-end gap-2 ${isUser ? 'justify-end' : ''}`}>
      {!isUser && (
        <div className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${NAVY}14` }}>
          <Bot className="w-4 h-4" style={{ color: NAVY }} />
        </div>
      )}
      <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed ${
        isUser ? 'text-white rounded-br-md' : 'bg-gray-100 text-gray-800 rounded-bl-md'
      }`} style={isUser ? { backgroundColor: NAVY } : {}}>
        {text}
      </div>
    </motion.div>
  );
}

export default function PatientConversationView() {
  const [messages, setMessages] = useState([{ role: 'ai', text: FLOWS.greeting.ai }]);
  const [chips, setChips] = useState(FLOWS.greeting.chips);
  const [started, setStarted] = useState(false);
  const bottomRef = useRef(null);

  // Only auto-scroll once the patient has started interacting, so the home screen
  // (greeting + reminders, with the app header) stays in view on first load.
  useEffect(() => { if (started) bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, started]);

  const send = (text) => {
    const key = resolveKey(text);
    const flow = FLOWS[key] || FLOWS.fallback;
    setStarted(true);
    setMessages((m) => [...m, { role: 'user', text }, { role: 'ai', text: flow.ai }]);
    setChips(flow.chips);
  };

  return (
    <MobilePhoneFrame>
      {/* App header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-gray-100 flex items-center gap-2.5" style={{ backgroundColor: NAVY }}>
        <div className="w-8 h-8 rounded-full bg-white/15 flex items-center justify-center">
          <HeartPulse className="w-4 h-4 text-white" />
        </div>
        <div className="leading-tight">
          <p className="text-white text-[13px] font-bold">RAIN Care</p>
          <p className="text-white/70 text-[10px]">Hi, {PATIENT.firstName} · University of Nevada, Reno</p>
        </div>
      </div>

      {/* Scrollable conversation */}
      <div className="flex-1 min-h-0 overflow-y-auto scrollbar-sleek px-4 py-4 bg-white">
        {/* Proactive reminders (home state only) */}
        {!started && (
          <div className="mb-4">
            <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2">Your reminders</p>
            <div className="space-y-2">
              {reminders.map((r) => {
                const Icon = r.icon;
                return (
                  <button key={r.title} onClick={() => send(r.chip)}
                    className="w-full text-left bg-white rounded-xl border border-gray-200 p-3 flex items-center gap-3 hover:border-gray-300 hover:shadow-sm transition-all cursor-pointer">
                    <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${r.tint}`}>
                      <Icon className="w-[18px] h-[18px]" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[13px] font-semibold text-gray-800">{r.title}</p>
                      <p className="text-[11px] text-gray-500">{r.detail}</p>
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="flex items-center gap-2 my-4">
              <div className="flex-1 h-px bg-gray-100" />
              <span className="text-[10px] font-semibold text-gray-300 uppercase tracking-wider">Ask me anything</span>
              <div className="flex-1 h-px bg-gray-100" />
            </div>
          </div>
        )}

        <div className="space-y-3">
          {messages.map((m, i) => <Bubble key={i} role={m.role} text={m.text} />)}
        </div>

        {/* Suggested questions */}
        {chips.length > 0 && (
          <div className="mt-3 flex flex-col gap-2 items-start">
            {chips.map((c) => (
              <button key={c} onClick={() => send(c)}
                className="text-left text-[13px] font-medium px-3.5 py-2 rounded-full border transition-all cursor-pointer"
                style={{ color: NAVY, borderColor: `${NAVY}33` }}>
                {c}
              </button>
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 px-3 py-3 border-t border-gray-100 bg-white">
        <ChatInput onSend={send} placeholder="Type a message…" suggestions={FLOWS.greeting.chips} />
        <p className="text-[9px] text-gray-300 text-center mt-2">Powered by Radiant Digital</p>
      </div>
    </MobilePhoneFrame>
  );
}
