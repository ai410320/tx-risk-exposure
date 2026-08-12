<script setup>
defineProps({
  text: { type: String, required: true },
})
</script>

<template>
  <span class="help-tip">
    <button type="button" class="help-tip__btn" aria-label="說明" tabindex="0">?</button>
    <span class="help-tip__bubble" role="tooltip">{{ text }}</span>
  </span>
</template>
