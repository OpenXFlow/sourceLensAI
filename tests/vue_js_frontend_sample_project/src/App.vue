<template>
  <div id="app">
    <nav>
      <router-link to="/">Home</router-link>
    </nav>
    <router-view/>
  </div>
</template>

<style>
  #app { font-family: Avenir, Helvetica, Arial, sans-serif; }
  nav { padding: 30px; }
</style>