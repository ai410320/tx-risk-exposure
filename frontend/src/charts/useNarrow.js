import { onBeforeUnmount, onMounted, ref } from 'vue'

/** 手機／窄螢幕：圖表改用較緊的邊距與較小字。 */
export function useNarrow(query = '(max-width: 900px)') {
  const narrow = ref(false)
  let mq = null

  function onChange(event) {
    narrow.value = Boolean(event.matches)
  }

  onMounted(() => {
    mq = window.matchMedia(query)
    narrow.value = mq.matches
    mq.addEventListener('change', onChange)
  })

  onBeforeUnmount(() => {
    mq?.removeEventListener('change', onChange)
  })

  return narrow
}
