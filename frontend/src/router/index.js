import { createRouter, createWebHistory } from 'vue-router'
import OverviewView from '../views/OverviewView.vue'
import OutlookView from '../views/OutlookView.vue'
import TrendView from '../views/TrendView.vue'
import MomentumView from '../views/MomentumView.vue'
import BreadthView from '../views/BreadthView.vue'
import ExternalView from '../views/ExternalView.vue'
import ChipView from '../views/ChipView.vue'
import MonthlyView from '../views/MonthlyView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'overview', component: OverviewView },
    { path: '/outlook', name: 'outlook', component: OutlookView },
    { path: '/trend', name: 'trend', component: TrendView },
    { path: '/momentum', name: 'momentum', component: MomentumView },
    { path: '/breadth', name: 'breadth', component: BreadthView },
    { path: '/chip', name: 'chip', component: ChipView },
    { path: '/external', name: 'external', component: ExternalView },
    { path: '/monthly', name: 'monthly', component: MonthlyView },
  ],
})
