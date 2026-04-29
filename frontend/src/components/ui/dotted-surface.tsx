import { cn } from '@/lib/utils'
import React, { useEffect, useRef } from 'react'
import * as THREE from 'three'

type DottedSurfaceProps = Omit<React.ComponentProps<'div'>, 'ref'>

export function DottedSurface({ className, ...props }: DottedSurfaceProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const sceneRef = useRef<{
    animationId: number
    renderer: THREE.WebGLRenderer
    scene: THREE.Scene
    material: THREE.PointsMaterial
  } | null>(null)

  // React to dark mode class changes
  useEffect(() => {
    const observer = new MutationObserver(() => {
      if (!sceneRef.current) return
      const isDark = document.documentElement.classList.contains('dark')
      sceneRef.current.material.opacity = isDark ? 0.55 : 0.75
    })
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!containerRef.current) return

    const SEPARATION = 150
    const AMOUNTX = 60
    const AMOUNTY = 60

    const scene = new THREE.Scene()

    const camera = new THREE.PerspectiveCamera(
      60,
      window.innerWidth / window.innerHeight,
      1,
      10000,
    )
    camera.position.set(0, 355, 1220)

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(window.devicePixelRatio)
    renderer.setSize(window.innerWidth, window.innerHeight)
    renderer.setClearColor(0x000000, 0)
    containerRef.current.appendChild(renderer.domElement)

    const positions: number[] = []
    const colors: number[] = []

    for (let ix = 0; ix < AMOUNTX; ix++) {
      for (let iy = 0; iy < AMOUNTY; iy++) {
        positions.push(
          ix * SEPARATION - (AMOUNTX * SEPARATION) / 2,
          0,
          iy * SEPARATION - (AMOUNTY * SEPARATION) / 2,
        )
        // #c9706a — terracotta, normalized to 0–1
        colors.push(0.788, 0.439, 0.416)
      }
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3))

    const material = new THREE.PointsMaterial({
      size: 12,
      vertexColors: true,
      transparent: true,
      opacity: 0.75,
      sizeAttenuation: true,
    })

    const points = new THREE.Points(geometry, material)
    scene.add(points)

    let count = 0
    let animationId: number = 0

    if (sceneRef.current) {
      sceneRef.current.material = material
    }

    const animate = () => {
      animationId = requestAnimationFrame(animate)
      const pos = geometry.attributes.position.array as Float32Array
      let i = 0
      for (let ix = 0; ix < AMOUNTX; ix++) {
        for (let iy = 0; iy < AMOUNTY; iy++) {
          pos[i * 3 + 1] =
            Math.sin((ix + count) * 0.3) * 50 +
            Math.sin((iy + count) * 0.5) * 50
          i++
        }
      }
      geometry.attributes.position.needsUpdate = true
      renderer.render(scene, camera)
      count += 0.07
    }

    const handleResize = () => {
      camera.aspect = window.innerWidth / window.innerHeight
      camera.updateProjectionMatrix()
      renderer.setSize(window.innerWidth, window.innerHeight)
    }

    window.addEventListener('resize', handleResize)
    animate()

    sceneRef.current = { animationId, renderer, scene, material }

    return () => {
      window.removeEventListener('resize', handleResize)
      if (sceneRef.current) {
        cancelAnimationFrame(sceneRef.current.animationId)
        sceneRef.current.scene.traverse(obj => {
          if (obj instanceof THREE.Points) {
            obj.geometry.dispose()
            if (Array.isArray(obj.material)) obj.material.forEach(m => m.dispose())
            else obj.material.dispose()
          }
        })
        sceneRef.current.renderer.dispose()
        if (containerRef.current && sceneRef.current.renderer.domElement) {
          containerRef.current.removeChild(sceneRef.current.renderer.domElement)
        }
      }
    }
  }, [])

  return (
    <div
      ref={containerRef}
      className={cn('pointer-events-none fixed inset-0', className)}
      {...props}
    />
  )
}
