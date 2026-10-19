import { BANK_TONES } from '../BubbleMap';

/** Inline, in-sentence colour key (not a legend box): "Colour shows the bank: ● B1 ● B2 ● B3." */
export function BankKey({ banks = ['B1', 'B2', 'B3'] }: { banks?: string[] }) {
  return (
    <span className="whitespace-nowrap">
      Colour shows the bank:
      {banks.map((b) => (
        <span key={b} className="ml-2 inline-flex items-center gap-1 text-ink">
          <span aria-hidden="true" className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: BANK_TONES[b] ?? '#999' }} />
          {b}
        </span>
      ))}
      .
    </span>
  );
}
