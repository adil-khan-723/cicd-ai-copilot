import { Settings, Sliders } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function SettingsPanel({ onOpenSetup }: { onOpenSetup: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-5 select-none">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface border border-glass">
        <Sliders className="h-6 w-6 text-text-dim" strokeWidth={1.5} />
      </div>
      <div className="text-center">
        <p className="text-sm font-semibold text-text-primary">Settings</p>
        <p className="text-xs text-text-dim mt-1.5 leading-relaxed">
          Update credentials or switch to a different project
        </p>
      </div>
      <Button variant="outline" size="sm" onClick={onOpenSetup} className="gap-2">
        <Settings className="h-3.5 w-3.5" strokeWidth={1.5} />
        Open Project Setup
      </Button>
    </div>
  )
}
