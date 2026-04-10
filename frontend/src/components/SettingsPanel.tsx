import { Button } from '@/components/ui/button'
import { Settings } from 'lucide-react'

interface SettingsPanelProps {
  onOpenSetup: () => void
}

export function SettingsPanel({ onOpenSetup }: SettingsPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-text-dim">
      <Settings className="h-8 w-8 opacity-20" />
      <div className="text-center">
        <p className="text-sm font-medium text-text-muted">Settings</p>
        <p className="text-xs mt-1">Update credentials or switch projects</p>
      </div>
      <Button variant="outline" size="sm" onClick={onOpenSetup} className="gap-2">
        <Settings className="h-3.5 w-3.5" />
        Open Project Setup
      </Button>
    </div>
  )
}
