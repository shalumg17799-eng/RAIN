/**
 * Draft the contracts of bespoke (tier 4) component types from what the app
 * actually sends: `npm run contracts:infer -- <namespace…> [--write] [--type <t>]`.
 *
 * For each bespoke type it reads every recorded answer of every persona that
 * draws it (the observed props), the persona manifests that bind it (title,
 * description, the component and its module), and the component's own source
 * (the defaults it applies to missing props, the variant values it handles).
 * From those it drafts a zod schema — field names, types, required vs optional
 * (a field missing from any recorded payload, or defaulted by the component,
 * is optional), nested objects, collections and maps — plus the variants the
 * props select and a pointer to a recorded example.
 *
 * Without --write it prints the draft. With --write it writes the namespace's
 * `contracts.ts` (refusing to overwrite one that exists unless --force): the
 * draft is a starting point a person owns from then on, and the contract test
 * (`core/catalog/contracts.test.ts`) keeps every recorded answer valid against
 * it. `--type <t>` prints the draft for one type — what `scaffold:component`
 * points at once a new bespoke type has its first recorded answer.
 */
import './lib/hydrate-from-backend'; // RAIN data: the backend's /api/v4/ui2/data snapshot, before any data module loads
import { existsSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { getMarkets } from '../src/core/runtime/registry';
import { CATALOG } from '../src/core/catalog/registry';
import { contractComponents, type ContractSpec } from '../src/core/contract/spec';
import { getContractNamespaces } from '../src/core/runtime/contracts';
import { listBespokeContracts, type BespokeContract } from '../src/core/catalog/contracts';
import { STATUSES } from '../src/core/contract/status';
import { z } from 'zod';

const APP = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(APP, 'src');
const args = process.argv.slice(2);
const flag = (n: string) => args.includes(`--${n}`);
const opt = (n: string) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : undefined; };
const namespaces = args.filter((a, i) => !a.startsWith('--') && !(args[i - 1] ?? '').startsWith('--type'));

/** Where each namespace's contracts file lives (the client that owns the types). */
export const NAMESPACE_FILES: Record<string, string> = {
  ussfcu: 'markets/financial-services/clients/ussfcu/contracts.ts',
  nfcu: 'markets/financial-services/clients/nfcu/contracts.ts',
  esfcu: 'markets/financial-services/clients/esfcu/contracts.ts',
  penfed: 'markets/financial-services/clients/penfed/contracts.ts',
  newfold: 'markets/commercial/clients/newfold-digital/contracts.ts',
  aramco: 'markets/oil-gas/clients/aramco/contracts.ts',
  att: 'markets/telecom/clients/att/contracts.ts',
  lyte: 'markets/telecom/clients/lyte-fiber/contracts.ts',
  doit: 'markets/sled/clients/doit/contracts.ts',
  amisa: 'markets/sled/clients/amisa/contracts.ts',
  md_comptroller: 'markets/sled/clients/md-comptroller/contracts.ts',
  sclac: 'markets/sled/clients/sclac/contracts.ts',
  rain: 'markets/sled/clients/rain/contracts.ts',
  reports: 'markets/platform/contracts.ts',
};

// ── observe ──────────────────────────────────────────────────────────────
const catalogTypes = new Set(CATALOG.map((e) => e.type));
const flatten = (specs: ContractSpec[]): ContractSpec[] => specs.flatMap((sp) => {
  const kids = Array.isArray(sp.props?.children) ? (sp.props.children as unknown[]).filter((c): c is ContractSpec => !!c && typeof c === 'object' && 'type' in (c as object)) : [];
  return [sp, ...flatten(kids)];
});
interface Decl { title: string; description: string; whyNotCatalog?: string; tenants: Set<string>; component: unknown }
const decls = new Map<string, Decl>();
const observed = new Map<string, Array<{ persona: string; flowKey: string; props: Record<string, unknown> }>>();
for (const market of getMarkets()) for (const client of market.clients) for (const persona of client.personas) {
  const m = (await persona.load()).default;
  for (const e of m.catalog ?? []) {
    // A binding written before the contracts carries the type's metadata; a
    // slimmed one carries only the component, and its client is the tenant.
    const d = decls.get(e.type) ?? { title: e.title ?? e.type, description: e.description ?? '', whyNotCatalog: e.whyNotCatalog, tenants: new Set<string>(), component: e.component };
    (e.tenants ?? [client.id]).forEach((t) => d.tenants.add(t));
    if (!d.description && e.description) d.description = e.description;
    decls.set(e.type, d);
  }
  for (const [flowKey, flow] of Object.entries(m.flows.chatFlows)) {
    const ui = (flow as { ui_components_to_render?: unknown[] }).ui_components_to_render ?? [];
    for (const sp of flatten([...contractComponents(ui), ...(m.answers?.({ flowKey, role: 'ai', uiComponents: ui }, m.signals ?? []) ?? [])])) {
      if (catalogTypes.has(sp.type)) continue;
      const { children: _c, ...props } = sp.props ?? {};
      if (!observed.has(sp.type)) observed.set(sp.type, []);
      observed.get(sp.type)!.push({ persona: persona.id, flowKey, props });
    }
  }
}

// ── what the existing contracts already say (owned by hand once drafted) ──
const existing = new Map<string, BespokeContract>();
for (const ns of getContractNamespaces()) for (const c of await listBespokeContracts(ns)) existing.set(c.type, c);
for (const [type, c] of existing) {
  const d = decls.get(type);
  if (d) { d.title = c.title; d.description = c.description; d.whyNotCatalog = c.whyNotCatalog; c.tenants.forEach((t) => d.tenants.add(t)); }
}
/** Paths of collections a contract declares non-empty (`.min(1)`), kept on a redraft. */
function nonEmptyPaths(schema: z.ZodType, path = '', out = new Set<string>()): Set<string> {
  let t: z.ZodType = schema;
  while (t instanceof z.ZodOptional || t instanceof z.ZodNullable || t instanceof z.ZodDefault) t = (t as unknown as { unwrap: () => z.ZodType }).unwrap();
  if (t instanceof z.ZodObject) for (const [k, v] of Object.entries(t.shape as Record<string, z.ZodType>)) nonEmptyPaths(v, path ? `${path}.${k}` : k, out);
  else if (t instanceof z.ZodArray) { if (!t.safeParse([]).success) out.add(path); nonEmptyPaths(t.element as z.ZodType, `${path}[]`, out); }
  else if (t instanceof z.ZodRecord) nonEmptyPaths((t as unknown as { valueType: z.ZodType }).valueType, `${path}{}`, out);
  else if (t instanceof z.ZodUnion) for (const o of (t as unknown as { options: z.ZodType[] }).options) nonEmptyPaths(o, path, out);
  return out;
}

// ── where each type's component lives (from the manifests that bind it) ──
function walk(d: string, out: string[] = []): string[] {
  for (const n of readdirSync(d)) { const p = join(d, n); if (statSync(p).isDirectory()) walk(p, out); else if (/\.(tsx?|jsx?)$/.test(n) && !n.includes('.test.')) out.push(p); }
  return out;
}
const manifestFiles = walk(join(SRC, 'markets'));
const implementation = new Map<string, string>();
/** Where `name` comes from in a module's source: `@/path` (default) or `@/path#Export` (named). */
function importOf(src: string, file: string, name: string): string | undefined {
  const rel = (p: string) => (p.startsWith('.') ? `@/${relative(SRC, join(dirname(file), p))}` : p);
  const dflt = src.match(new RegExp(`import\\s+${name}\\s*(?:,\\s*\\{[^}]*\\})?\\s+from\\s+['"]([^'"]+)['"]`));
  if (dflt) return rel(dflt[1]);
  for (const m of src.matchAll(/import\s*(?:\w+\s*,\s*)?\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]/g)) {
    for (const part of m[1].split(',').map((x) => x.trim()).filter(Boolean)) {
      const [orig, local] = part.split(/\s+as\s+/).map((x) => x.trim());
      if ((local ?? orig) === name) return `${rel(m[2])}#${orig}`;
    }
  }
  return undefined;
}
for (const f of manifestFiles) {
  const src = readFileSync(f, 'utf8');
  const bound = [
    ...[...src.matchAll(/bespoke\(\{\s*type:\s*["']([^"']+)["'][^]*?component:\s*([A-Za-z0-9_$]+)/g)].map((m) => [m[1], m[2]]),
    ...[...src.matchAll(/\bentry\(\s*["']([a-z_]+\.[a-z0-9_]+)["']\s*,\s*([A-Za-z0-9_$]+)\s*\)/g)].map((m) => [m[1], m[2]]),
  ];
  for (const [type, name] of bound) {
    if (implementation.has(type)) continue;
    implementation.set(type, importOf(src, f, name) ?? `@/${relative(SRC, f).replace(/\.(tsx?|jsx?)$/, '')}#${name}`);
  }
}
function resolveFile(spec: string): string | undefined {
  const base = join(SRC, spec.replace(/^@\//, '').replace(/#.*$/, ''));
  for (const ext of ['', '.tsx', '.jsx', '.ts', '.js', '/index.tsx', '/index.jsx', '/index.ts', '/index.js']) if (existsSync(base + ext) && statSync(base + ext).isFile()) return base + ext;
  return undefined;
}

// ── what the component itself does with missing props ─────────────────────
type Literal = string | number | boolean | null | unknown[] | Record<string, never>;
function literal(n: ts.Expression): { ok: true; v: Literal } | { ok: false } {
  if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) return { ok: true, v: n.text };
  if (ts.isNumericLiteral(n)) return { ok: true, v: Number(n.text) };
  if (ts.isPrefixUnaryExpression(n) && n.operator === ts.SyntaxKind.MinusToken && ts.isNumericLiteral(n.operand)) return { ok: true, v: -Number(n.operand.text) };
  if (n.kind === ts.SyntaxKind.TrueKeyword) return { ok: true, v: true };
  if (n.kind === ts.SyntaxKind.FalseKeyword) return { ok: true, v: false };
  if (n.kind === ts.SyntaxKind.NullKeyword) return { ok: true, v: null };
  if (ts.isArrayLiteralExpression(n) && n.elements.length === 0) return { ok: true, v: [] };
  if (ts.isObjectLiteralExpression(n) && n.properties.length === 0) return { ok: true, v: {} };
  return { ok: false };
}
/** The defaults in the component's props destructuring, and string values it compares props against. */
function componentFacts(file: string | undefined, exportName?: string): { defaults: Record<string, Literal>; computed: string[]; compared: Map<string, Set<string>>; summary?: string } {
  const facts: { defaults: Record<string, Literal>; computed: string[]; compared: Map<string, Set<string>>; summary?: string } = { defaults: {}, computed: [], compared: new Map() };
  if (!file) return facts;
  const text = readFileSync(file, 'utf8');
  facts.summary = docSummary(text, exportName);
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, file.endsWith('x') ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  let fn: ts.SignatureDeclaration | undefined;
  const isTarget = (name?: string, exported?: boolean) => (exportName ? name === exportName : exported);
  sf.forEachChild((node) => {
    if (fn) return;
    const mods = ts.canHaveModifiers(node) ? ts.getModifiers(node) ?? [] : [];
    const isDefault = mods.some((m) => m.kind === ts.SyntaxKind.DefaultKeyword);
    if (ts.isFunctionDeclaration(node) && isTarget(node.name?.text, isDefault)) fn = node;
    if (ts.isVariableStatement(node)) for (const d of node.declarationList.declarations) {
      if (ts.isIdentifier(d.name) && d.initializer && (ts.isArrowFunction(d.initializer) || ts.isFunctionExpression(d.initializer)) && exportName === d.name.text) fn = d.initializer;
    }
  });
  if (!fn && !exportName) {
    // `export default Name` / `export default memo(Name)`: find Name.
    let target: string | undefined;
    sf.forEachChild((node) => { if (ts.isExportAssignment(node)) { const e = node.expression; target = ts.isIdentifier(e) ? e.text : ts.isCallExpression(e) && e.arguments[0] && ts.isIdentifier(e.arguments[0]) ? e.arguments[0].text : undefined; } });
    if (target) return componentFacts(file, target);
  }
  const param = fn?.parameters[0];
  if (param && ts.isObjectBindingPattern(param.name)) {
    for (const el of param.name.elements) {
      const key = el.propertyName && ts.isIdentifier(el.propertyName) ? el.propertyName.text : ts.isIdentifier(el.name) ? el.name.text : undefined;
      if (!key || !el.initializer) continue;
      const lit = literal(el.initializer);
      if (lit.ok) facts.defaults[key] = lit.v; else facts.computed.push(key);
    }
  }
  for (const m of text.matchAll(/\b([a-zA-Z]+)\s*===\s*['"]([\w-]+)['"]/g)) {
    if (!facts.compared.has(m[1])) facts.compared.set(m[1], new Set());
    facts.compared.get(m[1])!.add(m[2]);
  }
  return facts;
}

/**
 * The first sentence of the component's own description: the comment directly
 * above its export (a doc block or `//` lines), else the file's opening comment
 * (one that sits before any code other than imports). Comments on helpers
 * inside the file are never used.
 */
function docSummary(text: string, exportName?: string): string | undefined {
  const lines = text.split('\n');
  const exportRe = exportName ? new RegExp(`^(export\\s+)?(default\\s+)?(function|const)\\s+${exportName}\\b`) : /^export\s+default\b/;
  const at = lines.findIndex((l) => exportRe.test(l));
  const blockEndingAt = (end: number): string[] | undefined => {
    let i = end;
    while (i >= 0 && !lines[i].trim()) i -= 1;
    if (i < 0) return undefined;
    if (lines[i].trim().endsWith('*/')) {
      let j = i;
      while (j >= 0 && !lines[j].includes('/*')) j -= 1;
      return j >= 0 ? lines.slice(j, i + 1) : undefined;
    }
    if (lines[i].trim().startsWith('//')) {
      let j = i;
      while (j > 0 && lines[j - 1].trim().startsWith('//')) j -= 1;
      return lines.slice(j, i + 1);
    }
    return undefined;
  };
  let block = at > 0 ? blockEndingAt(at - 1) : undefined;
  // A file that exports several components has an opening comment about the
  // file, not about this one: never borrow it (it gave five SideCards one
  // description, and an approval board its risk line's comment).
  const components = lines.filter((l) => /^export\s+(default\s+)?(function|const)\s+[A-Z]/.test(l)).length;
  if (!block && components <= 1) {
    // The opening comment: the first comment, provided only imports come before it.
    const first = lines.findIndex((l) => /^\s*(\/\*|\/\/)/.test(l));
    const code = lines.findIndex((l) => l.trim() && !/^\s*(import\b|\/\/|\/\*|\*|\}\s*from|['"])/.test(l) && !/^\s*[\w{},\s]+$/.test(l));
    if (first >= 0 && (code < 0 || first < code)) {
      let end = first;
      if (lines[first].includes('/*')) { while (end < lines.length && !lines[end].includes('*/')) end += 1; } else { while (end + 1 < lines.length && lines[end + 1].trim().startsWith('//')) end += 1; }
      block = lines.slice(first, end + 1);
    }
  }
  if (!block) return undefined;
  const prose = block.map((l) => l.replace(/^\s*(\/\*\*?|\*\/|\*|\/\/)\s?/, '').replace(/\*\/\s*$/, '').trim()).filter((l) => l && !l.startsWith('@') && !/^eslint-/.test(l)).join(' ').replace(/\s+/g, ' ').trim();
  const clean = prose.replace(/[─━═=]{3,}[^─━═=]*[─━═=]{3,}\s*/g, '').trim();
  if (clean.length < 12) return undefined;
  const sentence = (clean.match(/^.+?[.!?](?=\s|$)/) ?? [clean])[0];
  return sentence.length > 240 ? `${sentence.slice(0, 237)}…` : sentence;
}

// ── infer a shape from observed values ──────────────────────────────────
interface Shape { n: number; prims: Set<string>; strings: Set<string>; obj?: { n: number; fields: Map<string, { count: number; shape: Shape }> }; arr?: { n: number; nonEmpty: number; item?: Shape } }
const newShape = (): Shape => ({ n: 0, prims: new Set(), strings: new Set() });
function add(sh: Shape, v: unknown, depth = 0): Shape {
  sh.n += 1;
  if (Array.isArray(v)) {
    sh.arr ??= { n: 0, nonEmpty: 0 };
    sh.arr.n += 1;
    if (v.length) { sh.arr.nonEmpty += 1; sh.arr.item ??= newShape(); for (const x of v) add(sh.arr.item, x, depth + 1); }
  } else if (v && typeof v === 'object') {
    sh.obj ??= { n: 0, fields: new Map() };
    sh.obj.n += 1;
    for (const [k, x] of Object.entries(v)) {
      if (x === undefined) continue;
      const f = sh.obj.fields.get(k) ?? { count: 0, shape: newShape() };
      f.count += 1; add(f.shape, x, depth + 1);
      sh.obj.fields.set(k, f);
    }
  } else {
    const t = v === null ? 'null' : typeof v;
    sh.prims.add(t);
    if (t === 'string' && sh.strings.size < 40) sh.strings.add(v as string);
  }
  return sh;
}
const IDENT = /^[A-Za-z_$][A-Za-z0-9_$]*$/;
const key = (k: string) => (IDENT.test(k) ? k : JSON.stringify(k));
/** An object used as a map (ids or dates as keys, one value shape) is a record. */
function isRecord(o: NonNullable<Shape['obj']>): boolean {
  const keys = [...o.fields.keys()];
  if (keys.length < 6) return false;
  const shapes = [...o.fields.values()].map((f) => f.shape);
  if (!shapes.every((s) => s.obj && !s.arr && !s.prims.size)) return false;
  const sets = shapes.map((s) => new Set(s.obj!.fields.keys()));
  const all = new Set(sets.flatMap((s) => [...s]));
  const common = [...all].filter((k) => sets.every((s) => s.has(k)));
  const dataKeys = keys.filter((k) => /[\d\s:/-]/.test(k) || /^[A-Z0-9_]+$/.test(k)).length;
  return common.length / all.size >= 0.7 && (keys.length >= 12 || dataKeys / keys.length > 0.5);
}
function mergeShapes(a: Shape, b: Shape): Shape {
  const out = newShape();
  out.n = a.n + b.n;
  for (const s of [a, b]) { s.prims.forEach((p) => out.prims.add(p)); s.strings.forEach((x) => out.strings.size < 40 && out.strings.add(x)); }
  if (a.obj || b.obj) {
    out.obj = { n: (a.obj?.n ?? 0) + (b.obj?.n ?? 0), fields: new Map() };
    for (const s of [a, b]) for (const [k, f] of s.obj?.fields ?? []) {
      const prev = out.obj.fields.get(k);
      out.obj.fields.set(k, prev ? { count: prev.count + f.count, shape: mergeShapes(prev.shape, f.shape) } : { count: f.count, shape: f.shape });
    }
  }
  if (a.arr || b.arr) {
    const items = [a.arr?.item, b.arr?.item].filter(Boolean) as Shape[];
    out.arr = { n: (a.arr?.n ?? 0) + (b.arr?.n ?? 0), nonEmpty: (a.arr?.nonEmpty ?? 0) + (b.arr?.nonEmpty ?? 0), item: items.length ? items.reduce(mergeShapes) : undefined };
  }
  return out;
}
/** Field names that carry a state; their values are typed exactly (see stateSchema). */
const STATE_KEYS = new Set(['status', 'state', 'severity', 'tone', 'level']);
const STATUS_SET = new Set<string>(STATUSES);
interface EmitCtx { nonEmpty: Set<string>; compared: Map<string, Set<string>>; usesStatus: boolean }
let ctx: EmitCtx = { nonEmpty: new Set(), compared: new Map(), usesStatus: false };
/**
 * A state field's schema: the standard status vocabulary when every recorded
 * value is one of its five words; an enum of the documented values when they
 * are a small set of domain words (`pass`, `late`, `on_time`), widened by the
 * values the component itself compares against; otherwise null (free text).
 */
function stateSchema(k: string, sh: Shape): string | null {
  if (!STATE_KEYS.has(k) || sh.obj || sh.arr || sh.prims.size !== 1 || !sh.prims.has('string') || sh.strings.size >= 40) return null;
  const vals = [...sh.strings];
  if (vals.every((v) => STATUS_SET.has(v))) { ctx.usesStatus = true; return 'status'; }
  const word = /^[a-z][a-z0-9_]*$/;
  if (!vals.every((v) => word.test(v))) return null;
  const all = [...new Set([...vals, ...[...(ctx.compared.get(k) ?? [])].filter((v) => word.test(v))])].sort();
  return all.length <= 12 ? `z.enum([${all.map((v) => `'${v}'`).join(', ')}])` : null;
}
function emit(sh: Shape, ind: string, depth: number, path = ''): string {
  if (depth > 12) return 'z.unknown()';
  const parts: string[] = [];
  if (sh.obj) {
    if (isRecord(sh.obj)) {
      const value = [...sh.obj.fields.values()].map((f) => f.shape).reduce(mergeShapes);
      parts.push(`z.record(z.string(), ${emit(value, ind, depth + 1, `${path}{}`)})`);
    } else if (!sh.obj.fields.size) parts.push('z.object({})');
    else {
      const inner = `${ind}  `;
      const lines = [...sh.obj.fields.entries()].map(([k, f]) => `${inner}${key(k)}: ${stateSchema(k, f.shape) ?? emit(f.shape, inner, depth + 1, path ? `${path}.${k}` : k)}${f.count < sh.obj!.n ? '.optional()' : ''},`);
      parts.push(`z.object({\n${lines.join('\n')}\n${ind}})`);
    }
  }
  if (sh.arr) parts.push(`z.array(${sh.arr.item ? emit(sh.arr.item, ind, depth + 1, `${path}[]`) : 'z.unknown()'})${ctx.nonEmpty.has(path) ? '.min(1)' : ''}`);
  for (const p of ['string', 'number', 'boolean']) if (sh.prims.has(p)) parts.push(`z.${p}()`);
  const nullable = sh.prims.has('null');
  if (!parts.length) return nullable ? 'z.null()' : 'z.unknown()';
  const body = parts.length === 1 ? parts[0] : `z.union([${parts.join(', ')}])`;
  return nullable ? `${body}.nullable()` : body;
}

/** A variant name is a generic kebab word, whatever the prop value's spelling. */
const kebab = (v: string) => v.replace(/([a-z0-9])([A-Z])/g, '$1-$2').replace(/[\s_]+/g, '-').toLowerCase();

// ── variants ─────────────────────────────────────────────────────────────
const VARIANT_KEYS = ['variant', 'mode', 'layout', 'view', 'size', 'density', 'compact', 'expanded', 'dense', 'condensed', 'inline', 'mini'];
interface DraftVariant { name: string; description: string; when?: Record<string, string | boolean> }
function variantsOf(top: Shape | undefined, defaults: Record<string, Literal>, compared: Map<string, Set<string>>): { variants: DraftVariant[]; enums: Map<string, string[]> } {
  const variants: DraftVariant[] = []; const enums = new Map<string, string[]>();
  for (const k of VARIANT_KEYS) {
    const f = top?.obj?.fields.get(k);
    if (!f) continue;
    const s = f.shape;
    if (s.prims.size === 1 && s.prims.has('boolean')) {
      variants.push({ name: k, description: `Drawn with \`${k}: true\`.`, when: { [k]: true } });
    } else if (s.prims.size === 1 && s.prims.has('string') && !s.obj && !s.arr) {
      const values = [...new Set([...s.strings, ...(compared.get(k) ?? []), ...(typeof defaults[k] === 'string' ? [defaults[k] as string] : [])])].sort();
      if (values.length > 8) continue;
      enums.set(k, values);
      const dflt = typeof defaults[k] === 'string' ? (defaults[k] as string) : undefined;
      for (const v of values) variants.push({ name: kebab(v), description: `Drawn with \`${k}: '${v}'\`${v === dflt ? ' (the default)' : ''}.`, ...(v === dflt ? {} : { when: { [k]: v } }) });
    }
  }
  return { variants, enums };
}

// ── draft one type ───────────────────────────────────────────────────────
const q = (s: string) => `'${s.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n')}'`;
function draft(type: string): { text: string; fields: Map<string, string> } {
  const d = decls.get(type);
  const obs = observed.get(type) ?? [];
  const impl = implementation.get(type) ?? '(unbound)';
  const [modulePath, exportName] = impl.split('#');
  const facts = componentFacts(resolveFile(modulePath), exportName);
  const prior = existing.get(type);
  ctx = { nonEmpty: prior ? nonEmptyPaths(prior.schema) : new Set(), compared: facts.compared, usesStatus: ctx.usesStatus };
  const top = obs.map((o) => add(newShape(), o.props)).reduce<Shape | undefined>((a, b) => (a ? mergeShapes(a, b) : b), undefined);
  const { variants, enums } = variantsOf(top, facts.defaults, facts.compared);
  const fields = new Map<string, string>();
  const n = top?.obj?.n ?? 0;
  for (const [k, f] of top?.obj?.fields ?? []) {
    const base = enums.has(k) ? `z.enum([${enums.get(k)!.map(q).join(', ')}])` : (stateSchema(k, f.shape) ?? emit(f.shape, '    ', 1, k));
    const optional = f.count < n || k in facts.defaults || facts.computed.includes(k);
    fields.set(k, `${base}${optional ? '.optional()' : ''}`);
  }
  for (const [k, v] of Object.entries(facts.defaults)) {
    if (fields.has(k) || /^on[A-Z]/.test(k) || /^(render|get|format)[A-Z]/.test(k) || k === 'children') continue;
    const vals = typeof v === 'string' ? [...new Set([v, ...(VARIANT_KEYS.includes(k) ? facts.compared.get(k) ?? [] : [])])].sort() : [];
    const base = typeof v === 'string' ? (vals.length > 1 ? `z.enum([${vals.map(q).join(', ')}])` : 'z.string()')
      : typeof v === 'number' ? 'z.number()' : typeof v === 'boolean' ? 'z.boolean()' : Array.isArray(v) ? 'z.array(z.unknown())' : v === null ? 'z.unknown()' : 'z.record(z.string(), z.unknown())';
    fields.set(k, `${base}.optional()`);
    if (VARIANT_KEYS.includes(k) && vals.length > 1 && !variants.some((x) => x.when && k in x.when)) {
      for (const val of vals) variants.push(val === v ? { name: kebab(val), description: `Drawn with \`${k}: '${val}'\` (the default).` } : { name: kebab(val), description: `Drawn with \`${k}: '${val}'\`.`, when: { [k]: val } });
    } else if (VARIANT_KEYS.includes(k) && typeof v === 'boolean' && !variants.some((x) => x.when && k in x.when)) {
      variants.push({ name: k, description: `Drawn with \`${k}: true\`.`, when: { [k]: true } });
    }
  }
  const defaultCount = variants.filter((x) => !x.when).length;
  if (defaultCount > 1) { const keep = variants.find((x) => !x.when && x.name !== 'default'); for (let i = variants.length - 1; i >= 0; i--) if (!variants[i].when && variants[i] !== keep) variants.splice(i, 1); }
  if (variants.length && !variants.some((x) => !x.when)) variants.unshift({ name: 'default', description: 'Drawn when no variant prop is set.' });
  const declared = d?.description ?? '';
  const description = /drawn in this tenant's answers/.test(declared) && facts.summary ? facts.summary : declared;
  const smallest = [...obs].sort((a, b) => JSON.stringify(a.props).length - JSON.stringify(b.props).length)[0];
  const defaults = Object.fromEntries(Object.entries(facts.defaults).filter(([k]) => fields.has(k)));
  const lines = [
    '  {',
    `    type: ${q(type)},`,
    '    version: 1,',
    `    title: ${q(d?.title ?? type)},`,
    `    description: ${q(description)},`,
    ...(d?.whyNotCatalog ? [`    whyNotCatalog: ${q(d.whyNotCatalog)},`] : []),
    `    tenants: [${[...(d?.tenants ?? [])].sort().map(q).join(', ')}],`,
    `    implementation: ${q(impl)},`,
    ...(smallest ? [`    example: { persona: ${q(smallest.persona)}, flowKey: ${q(smallest.flowKey)} },`] : []),
    ...(Object.keys(defaults).length ? [`    defaults: ${JSON.stringify(defaults).replace(/"([A-Za-z_$][\w$]*)":/g, '$1: ')},`] : []),
    ...(variants.length ? ['    variants: [', ...variants.map((v) => `      { name: ${q(v.name)}, description: ${q(v.description)}${v.when ? `, when: ${JSON.stringify(v.when).replace(/"([A-Za-z_$][\w$]*)":/g, '$1: ')}` : ''} },`), '    ],'] : []),
    `    schema: z.object({${fields.size ? '' : '}),'}`,
  ];
  return { text: lines.join('\n'), fields };
}

/** Write a namespace's file: shared field schemas hoisted into named constants. */
function fileFor(ns: string, types: string[]): string {
  ctx.usesStatus = false;
  const drafts = types.map((t) => ({ t, ...draft(t) }));
  const count = new Map<string, number>();
  for (const d of drafts) for (const [, s] of d.fields) if (s.length > 160) count.set(s, (count.get(s) ?? 0) + 1);
  const hoisted = new Map<string, string>(); const used = new Set<string>();
  for (const d of drafts) for (const [k, s] of d.fields) {
    if ((count.get(s) ?? 0) < 2 || hoisted.has(s)) continue;
    let name = k.replace(/[^A-Za-z0-9_$]/g, '_'); let i = 2;
    while (used.has(name)) name = `${k}${i++}`;
    used.add(name); hoisted.set(s, name);
  }
  const consts = [...hoisted.entries()].map(([s, name]) => {
    const opt = s.endsWith('.optional()');
    return `/** Shared by several types below. */\nconst ${name} = ${(opt ? s.slice(0, -'.optional()'.length) : s).replace(/\n {4}/g, '\n')};`;
  });
  const body = drafts.map((d) => {
    const fieldLines = [...d.fields.entries()].map(([k, s]) => {
      const h = hoisted.get(s) ?? (s.endsWith('.optional()') ? hoisted.get(s) : undefined);
      const opt = s.endsWith('.optional()');
      const named = hoisted.get(s);
      return `      ${key(k)}: ${named ? `${named}${opt ? '.optional()' : ''}` : s.replace(/\n/g, '\n  ')},`;
      void h;
    });
    return d.fields.size ? `${d.text}\n${fieldLines.join('\n')}\n    }),\n  },` : `${d.text}\n  },`;
  });
  return [
    '/**',
    ` * Contracts of the \`${ns}.*\` bespoke (tier 4) component types: identity,`,
    ' * version, the props each takes, the defaults the component applies, its',
    ' * variants and where the implementation lives (core/catalog/contracts.ts).',
    ' *',
    ' * First drafted from the recorded answers by `npm run contracts:infer`, then',
    ' * owned here: when a component\'s props change, change its schema in the same',
    ' * commit. `core/catalog/contracts.test.ts` fails if a recorded answer stops',
    ' * matching, a binding points at another component, or a type is missing.',
    ' * Objects are open (extra fields pass); a field is optional when a recorded',
    ' * answer omits it or the component defaults it. A state field uses the',
    ' * standard status vocabulary where its values are those words, else the enum',
    ' * of the domain values the component draws; free text stays a string.',
    ' */',
    "import { z } from 'zod';",
    "import { defineContracts } from '@core/catalog/contracts';",
    ...(ctx.usesStatus ? ["import { STATUSES } from '@core/contract/status';", '', '/** The standard status vocabulary (good · warning · critical · info · neutral). */', 'const status = z.enum(STATUSES);'] : []),
    '',
    ...(consts.length ? [...consts, ''] : []),
    'export default defineContracts([',
    ...body,
    ']);',
    '',
  ].join('\n');
}

if (flag('fix-implementations')) {
  // Rewrite only the `implementation:` line of each existing contract, from the bindings.
  for (const rel of Object.values(NAMESPACE_FILES)) {
    const file = join(SRC, rel);
    if (!existsSync(file)) continue;
    let text = readFileSync(file, 'utf8'); let n = 0;
    text = text.replace(/(type: '([^']+)',[^]*?implementation: )'([^']*)'/g, (all, head, type, was) => {
      const now = implementation.get(type);
      if (!now || now === was) return all;
      n += 1; return `${head}'${now}'`;
    });
    if (n) { writeFileSync(file, text); console.log(`${rel}: ${n} implementation(s) corrected`); }
  }
  process.exit(0);
}

const single = opt('type');
if (single) {
  console.log(fileFor(single.split('.')[0], [single]));
  process.exit(0);
}
const nsOf = (t: string) => t.slice(0, t.indexOf('.'));
const allNs = [...new Set([...decls.keys()].map(nsOf))].sort();
const targets = namespaces.length ? namespaces : allNs;
for (const ns of targets) {
  const types = [...decls.keys()].filter((t) => nsOf(t) === ns).sort();
  const text = fileFor(ns, types);
  const rel = NAMESPACE_FILES[ns];
  if (!flag('write') || !rel) { console.log(text); if (!rel) console.error(`No file location for namespace "${ns}": add it to NAMESPACE_FILES.`); continue; }
  const file = join(SRC, rel);
  if (existsSync(file) && !flag('force')) { console.error(`${rel} exists — not overwritten (use --force to redraft).`); continue; }
  writeFileSync(file, text);
  console.log(`Wrote ${types.length} contracts to src/${rel}`);
}
process.exit(0);
