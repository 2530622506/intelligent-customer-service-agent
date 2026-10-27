import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'
import { Check, LoaderCircle, OctagonAlert } from 'lucide-react'

export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

export function cn(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(' ')
}

export function Panel({ className, children, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn('panel', className)} {...props}>{children}</section>
}

export function PanelHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="panel-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2 className="panel-title">{title}</h2>
        {description ? <p className="panel-description">{description}</p> : null}
      </div>
      {action ? <div className="panel-header-action">{action}</div> : null}
    </div>
  )
}

export function Button({ className, tone = 'neutral', size = 'md', icon, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tone?: Tone; size?: 'sm' | 'md' | 'lg'; icon?: ReactNode }) {
  return <button className={cn('button', `button-${tone}`, `button-${size}`, className)} {...props}>{icon}{children}</button>
}

export function IconButton({ label, className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className={cn('icon-button', className)} aria-label={label} title={label} {...props}>{children}</button>
}

export function StatusPill({ tone = 'neutral', children, pulse = false }: { tone?: Tone; children: ReactNode; pulse?: boolean }) {
  return <span className={cn('status-pill', `status-${tone}`, pulse && 'status-pulse')}><span className="status-dot" />{children}</span>
}

export function MetricTile({ label, value, detail, icon, tone = 'neutral' }: { label: string; value: string | number; detail?: string; icon?: ReactNode; tone?: Tone }) {
  return (
    <div className={cn('metric-tile', `metric-${tone}`)}>
      <div className="metric-topline"><span className="metric-label">{label}</span>{icon ? <span className="metric-icon">{icon}</span> : null}</div>
      <strong className="metric-value">{value}</strong>
      {detail ? <span className="metric-detail">{detail}</span> : null}
    </div>
  )
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon}</div><h3>{title}</h3><p>{description}</p>{action ? <div className="empty-action">{action}</div> : null}</div>
}

export function LoadingState({ label = '正在加载' }: { label?: string }) {
  return <div className="loading-state"><LoaderCircle className="spin" size={18} />{label}</div>
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-state"><OctagonAlert size={18} /><div><strong>出了点问题</strong><p>{message}</p>{onRetry ? <button className="text-link" type="button" onClick={onRetry}>重新加载</button> : null}</div></div>
}

export function SuccessMark({ label }: { label: string }) {
  return <span className="success-mark"><Check size={14} />{label}</span>
}

export function SectionDivider() {
  return <div className="section-divider" />
}
