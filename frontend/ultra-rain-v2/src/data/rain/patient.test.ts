/**
 * Linda Garcia, the patient (spec v2.1, Use Case C): her contract holds its
 * shape, the spec's English and Spanish lines are on screen word for word,
 * her readings follow the goal and safety rules, typed questions route, and
 * each of her steps lands in the care team's store (Use Case C into A and B).
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { rainClient } from '@/markets/sled/clients/rain/client.manifest';
import patientM from '@/markets/sled/clients/rain/personas/patient/manifest';
import {
  approveLindaRequest,
  getRainState,
  lindaAfterVisit,
  lindaAsk,
  lindaOpenLink,
  lindaShareReading,
  lindaSignedIn,
  resetRainState,
  setLindaLang,
} from '@/components/value-based-care/shell/store';
import * as C from './_shared/constants';
import { CONTRACT_KEYS, WORKBENCHES } from './_shared/contract';
import type { PatientStepId } from './_shared/patient';
import { PATIENT, UI, isUrgent, matchQuestion, meetsGoal, readingPoints, readingReply } from './_shared/patient';

const ids = Object.keys(PATIENT.steps) as PatientStepId[];

describe('Linda: contract', () => {
  it('has exactly the seven fixed top-level keys, like every RAIN persona', () => {
    expect(Object.keys(PATIENT).sort()).toEqual([...CONTRACT_KEYS].sort());
    expect(PATIENT.kpis).toEqual([]);
    expect(PATIENT.workbenches).toEqual([]);
  });

  it('routes every chip, card and suggested question to a step that exists', () => {
    for (const id of ids) for (const c of PATIENT.steps[id].chips) expect(PATIENT.steps[c], `${id} → ${c}`).toBeDefined();
    for (const card of PATIENT.signals) expect(PATIENT.steps[card.chip], card.id).toBeDefined();
    for (const q of PATIENT.queries) expect(PATIENT.steps[q.to], q.en).toBeDefined();
  });

  it('ships every string in English and Spanish', () => {
    for (const id of ids) {
      const s = PATIENT.steps[id];
      for (const b of [s.label, s.ai, s.aiAfter, s.aiMobile].filter(Boolean)) {
        expect(b!.en.trim().length, `${id} en`).toBeGreaterThan(0);
        expect(b!.es.trim().length, `${id} es`).toBeGreaterThan(0);
        expect(b!.es, `${id} is translated`).not.toBe(b!.en);
      }
    }
    for (const [k, b] of Object.entries(UI)) if (k !== 'brand') expect(b.es, k).not.toBe(b.en);
  });

  it('names connections into workbenches that exist, with no other patient in them', () => {
    const connected = new Set(ids.flatMap((id) => PATIENT.steps[id].connects ?? []));
    for (const h of PATIENT.handoffs) {
      expect(WORKBENCHES[h.workbench], h.id).toBeDefined();
      expect(connected.has(h.id), `${h.id} is made by a step`).toBe(true);
    }
  });
});

describe('Linda: spec wording (English by default, Spanish ships)', () => {
  const step = (id: PatientStepId) => PATIENT.steps[id];

  it('scripts the four guided steps verbatim in both languages', () => {
    expect(step('pt_week').ai.en).toBe(
      'Hi Linda! Here is what is coming up this week: 1) Take your blood pressure today. 2) Video visit with your care team on Thursday at 2:00 PM. No drive needed. 3) Your metformin refill is due Sunday. What would you like to do first?',
    );
    expect(step('pt_week').ai.es).toBe(
      '¡Hola Linda! Esto es lo que tiene esta semana: 1) Tómese la presión hoy. 2) Cita por video con su equipo de salud el jueves a las 2:00 PM. No tiene que manejar. 3) Su metformina se renueva el domingo. ¿Qué quiere hacer primero?',
    );
    expect(step('pt_drive').ai.en).toBe(
      'Yes. You already have a video visit on Thursday at 2:00 PM, and you can join from this phone. If you would rather see someone in person, the mobile clinic is in Battle Mountain next Tuesday, about 10 minutes from you. If you need to go to the clinic in Winnemucca, your health plan covers a free ride. Do you want to keep Thursday, switch to the mobile clinic, or ask for a ride?',
    );
    expect(step('pt_drive').ai.es).toBe(
      'Sí. Ya tiene una cita por video el jueves a las 2:00 PM y puede entrar desde este teléfono. Si prefiere ver a alguien en persona, la clínica móvil estará en Battle Mountain el próximo martes, a unos 10 minutos de usted. Si necesita ir a la clínica en Winnemucca, su plan de salud cubre un viaje gratis. ¿Quiere mantener la cita del jueves, cambiar a la clínica móvil o pedir un viaje?',
    );
    expect(step('pt_after').ai.en).toBe(
      'Thank you for your visit, Linda. Here is your summary from your care team: Your blood pressure today was 136 over 84. That meets your goal. Keep taking your medicine the same way. Your metformin refill is on its way by mail and should arrive Saturday. Next step: take your blood pressure once a week and add it here. We will remind you.',
    );
    expect(step('pt_after').ai.es).toBe(
      'Gracias por su cita, Linda. Este es el resumen de su equipo de salud: Su presión hoy fue 136 sobre 84. Eso cumple su meta. Siga tomando su medicina igual. Su metformina ya va en camino por correo y debe llegar el sábado. Siguiente paso: tómese la presión una vez por semana y anótela aquí. Le vamos a recordar.',
    );
  });

  it('answers her 142/88 home reading with the spec sentence, in both languages', () => {
    expect(readingReply(C.LINDA.home, 'en')).toBe(
      'Thank you, Linda. Your reading is 142 over 88. That is better than your last one in August (148 over 92). Your goal is under 140 over 90, so you are close. Your care team will see this before your video visit on Thursday.',
    );
    expect(readingReply(C.LINDA.home, 'es')).toBe(
      'Gracias, Linda. Su presión es 142 sobre 88. Está mejor que la última vez en agosto (148 sobre 92). Su meta es menos de 140 sobre 90, así que está cerca. Su equipo de salud la verá antes de su cita del jueves.',
    );
    expect(PATIENT.steps.pt_bp_result.ai.en).toBe(readingReply(C.LINDA.home, 'en'));
    expect(PATIENT.steps.pt_bp_result.ai.es).toBe(readingReply(C.LINDA.home, 'es'));
  });

  it('shows the three this-week cards and the chips the spec lists', () => {
    expect(PATIENT.signals.map((c) => [c.title.en, c.when.en, c.text.en])).toEqual([
      ['Take your blood pressure', 'Today', 'Your care team asked for a reading before Thursday.'],
      ['Video visit', 'Thursday, Nov 5, 2:00 PM', 'Join from this phone. No drive needed.'],
      ['Metformin refill', 'Due Sunday, Nov 8', 'We can mail it to you.'],
    ]);
    const labels = (id: PatientStepId) => PATIENT.steps[id].chips.map((c) => PATIENT.steps[c].label.en);
    expect(labels('pt_week')).toEqual(['Add my blood pressure', 'About my video visit', 'Refill my medicine']);
    expect(labels('pt_bp_result')).toEqual(['Can I see the doctor without driving?', 'Show my readings', 'Refill my medicine']);
    expect(labels('pt_drive')).toEqual(['Keep Thursday', 'Switch to the mobile clinic', 'Ask for a ride']);
    expect(labels('pt_after')).toEqual(['Show my readings', 'When is my next visit?', 'Talk to my care team']);
  });

  it('lists the six suggested questions in both languages', () => {
    expect(PATIENT.queries.map((q) => `${q.en} / ${q.es}`)).toEqual([
      'When is my next visit? / ¿Cuándo es mi próxima cita?',
      'How do I join my video visit? / ¿Cómo entro a mi cita por video?',
      'I need a ride / Necesito un viaje',
      'Refill my medicine / Renovar mi medicina',
      'Show my blood pressure readings / Ver mis lecturas de presión',
      'Talk to my care team / Hablar con mi equipo de salud',
    ]);
  });

  it('uses the clinic brand first and the fixed safety wording', () => {
    expect(UI.brand.en).toBe('Sierra Basin Care');
    expect(UI.urgent.en).toBe('This reading is high. We let your care team know. If you have chest pain, trouble breathing or a bad headache, call 911.');
    expect(UI.switchTo).toEqual({ en: 'Español', es: 'English' });
  });
});

describe('Linda: readings and typed questions', () => {
  it('holds the goal and the safety line', () => {
    expect(meetsGoal(C.LINDA.home)).toBe(false);
    expect(meetsGoal(C.LINDA.visitReading)).toBe(true);
    expect(isUrgent({ sys: 180, dia: 100 })).toBe(true);
    expect(isUrgent({ sys: 150, dia: 110 })).toBe(true);
    expect(isUrgent({ sys: 179, dia: 109 })).toBe(false);
    expect(readingReply({ sys: 182, dia: 112 }, 'en')).toBe('Thank you, Linda. Your reading is 182 over 112.');
    expect(readingReply({ sys: 136, dia: 84 }, 'en')).toContain('That meets your goal of under 140 over 90.');
  });

  it('trends her last three readings, oldest first', () => {
    expect(readingPoints({ homeReading: null, afterVisit: false }, 'en').map((p) => C.bpText(p.r))).toEqual(['152/94', '148/92']);
    expect(readingPoints({ homeReading: C.LINDA.home, afterVisit: false }, 'en').map((p) => C.bpText(p.r))).toEqual(['152/94', '148/92', '142/88']);
    expect(readingPoints({ homeReading: C.LINDA.home, afterVisit: true }, 'en').map((p) => C.bpText(p.r))).toEqual(['148/92', '142/88', '136/84']);
  });

  it.each([
    ['Can I see the doctor without driving?', 'pt_drive'],
    ['¿Puedo ver al doctor sin manejar?', 'pt_drive'],
    ['I need a ride', 'pt_drive'],
    ['Keep Thursday', 'pt_keep'],
    ['When is my next visit?', 'pt_next'],
    ['¿Cuándo es mi próxima cita?', 'pt_next'],
    ['refill my metformin please', 'pt_refill'],
    ['Should I take my pill before the visit?', 'pt_clinical'],
    ['¿Debo tomar mi pastilla?', 'pt_clinical'],
    ['I want to add my blood pressure', 'pt_bp'],
    ['What is the weather?', 'pt_fallback'],
  ])('routes "%s" to %s', (text, step) => {
    expect(matchQuestion(text)).toBe(step);
  });
});

describe('Linda: Use Case C feeds A and B', () => {
  beforeEach(resetRainState);

  it('opens the link: the visit is on file and the 72-hour reminder is read', () => {
    lindaOpenLink();
    const s = getRainState();
    expect(s.linda.opened).toBe(true);
    expect(s.bookings['M-40107']).toBe('S1');
    expect(s.campaign.booked).toBe(C.CARE.booked + 1);
    lindaSignedIn();
    expect(getRainState().linda.thread.map((t) => t.step)).toEqual(['pt_week']);
  });

  it('shares 142/88 without closing her gap; an urgent reading alerts the Worklist', () => {
    lindaShareReading(C.LINDA.home);
    expect(getRainState().linda.homeReading).toEqual(C.LINDA.home);
    expect(getRainState().linda.alert).toBeNull();
    expect(getRainState().campaign.controlled).toBe(C.CARE.controlled);
    lindaShareReading({ sys: 184, dia: 112 });
    expect(getRainState().linda.alert).toEqual({ sys: 184, dia: 112 });
  });

  it('keeps Thursday, then the visit closes her gap once: campaign and quality tracker up by one', () => {
    lindaAsk('pt_keep');
    expect(getRainState().linda.visit).toBe('keep');
    lindaAfterVisit();
    lindaAfterVisit();
    const s = getRainState();
    expect(s.lindaReading).toBe(true);
    expect(s.campaign.controlled).toBe(C.CARE.controlled + 1);
    expect(s.linda.refillMailed).toBe(true);
    expect(s.linda.thread.filter((t) => t.step === 'pt_after')).toHaveLength(1);
  });

  it('sends a mobile clinic switch for staff approval; approving moves the booking', () => {
    lindaOpenLink();
    lindaAsk('pt_mobile');
    expect(getRainState().linda.requestApproved).toBe(false);
    approveLindaRequest();
    expect(getRainState().bookings['M-40107']).toBe('S4');
    lindaAsk('pt_next');
    expect(getRainState().linda.thread.at(-1)!.mobile).toBe(true);
  });

  it('routes a clinical question to the care team and remembers her language until the demo resets', () => {
    lindaAsk('pt_clinical', 'Should I take my pill?');
    expect(getRainState().linda.message).toBe(true);
    setLindaLang('es');
    expect(getRainState().linda.lang).toBe('es');
    resetRainState();
    expect(getRainState().linda.lang).toBe('en');
  });
});

describe('Linda: persona', () => {
  it('is the last persona in the switcher and opens her phone view only', () => {
    expect(rainClient.personas.at(-1)!.id).toBe(C.PATIENT_PERSONA_ID);
    expect(rainClient.defaultPersonaId).toBe(C.PERSONAS.ceo);
    expect(patientM.id).toBe(C.PATIENT_PERSONA_ID);
    expect(patientM.features?.navSlots).toEqual(['ask']);
    expect(patientM.initialExtras).toBeDefined();
    expect(patientM.signals).toEqual([]);
  });
});
