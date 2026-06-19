// ============================================================================
// FalconFX.mq5 — MT5 Expert Advisor
// FalconFX Strategy Handbook Implementation (Mark Hutchinson)
// 
// Main EA that combines:
//   - Nature Theory (impulsive vs corrective)
//   - Market Structure (breathing cycle, HH/HL, LH/LL)
//   - Entry Types (Risk + Reduced Risk)
//   - Trade Management (B/E, Half-Risk, 90% Rule, Scaling In)
//   - Risk Guards (max 2/day, 1% cap, session filter)
//
// Installation: Copy to MQL5/Experts/ folder, compile in MetaEditor
// Backtest: Use MT5 Strategy Tester with "Every tick" mode
// ============================================================================

#property copyright "FalconFX Bot v3.0 — Handbook Edition"
#property link      "https://github.com/bytebridge035-wq/falconfx_ai_bot"
#property version   "3.00"
#property strict

// ═══════════════════════════════════════════════════════════════════════════
// INCLUDES
// ═══════════════════════════════════════════════════════════════════════════

#include "FalconFX_Utils.mqh"
#include "FalconFX_Management.mqh"

// ═══════════════════════════════════════════════════════════════════════════
// EA INPUTS (override group names for clarity)
// ═══════════════════════════════════════════════════════════════════════════

input group "═══ FALCONFX BOT v3.0 ═══"
input string InpComment = "FalconFX";    // Order comment prefix

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL VARIABLES
// ═══════════════════════════════════════════════════════════════════════════

bool g_lastSignalLong  = false;
bool g_lastSignalShort = false;

// ═══════════════════════════════════════════════════════════════════════════
// EXPERT INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

int OnInit()
{
   Print("══════════════════════════════════════════");
   Print("  FalconFX Bot v3.0 — Handbook Edition");
   Print("  Based on FalconFX Strategy Handbook P1-38");
   Print("══════════════════════════════════════════");
   
   if(!FalconFX_Init())
   {
      Print("FalconFX: Initialization failed!");
      return INIT_FAILED;
   }
   
   if(!FalconFX_MgmtInit())
   {
      Print("FalconFX: Management initialization failed!");
      return INIT_FAILED;
   }
   
   // Reset state
   g_lastSignalLong  = false;
   g_lastSignalShort = false;
   
   return INIT_SUCCEEDED;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPERT DEINITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

void OnDeinit(const int reason)
{
   FalconFX_Deinit();
   Print("FalconFX Bot stopped. Reason: ", reason);
}

// ═══════════════════════════════════════════════════════════════════════════
// CHECK IF WE ALREADY HAVE AN OPEN POSITION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == FALCONFX_MAGIC)
         return true;
   }
   return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// CALCULATE STOP LOSS FOR LONG
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_CalculateLongSL()
{
   double atr = FalconFX_GetATR(0);
   
   // Use structure support level if available
   if(g_supportLevel > 0)
      return g_supportLevel - atr * 0.3;
   
   // Fallback: ATR-based
   return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - atr * 1.5;
}

// ═══════════════════════════════════════════════════════════════════════════
// CALCULATE STOP LOSS FOR SHORT
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_CalculateShortSL()
{
   double atr = FalconFX_GetATR(0);
   
   if(g_resistanceLevel > 0)
      return g_resistanceLevel + atr * 0.3;
   
   return SymbolInfoDouble(_Symbol, SYMBOL_BID) + atr * 1.5;
}

// ═══════════════════════════════════════════════════════════════════════════
// CALCULATE TAKE PROFIT
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_CalculateLongTP(double entryPrice, double sl)
{
   double risk = MathAbs(entryPrice - sl);
   return entryPrice + risk * InpTPRatio;
}

double FalconFX_CalculateShortTP(double entryPrice, double sl)
{
   double risk = MathAbs(sl - entryPrice);
   return entryPrice - risk * InpTPRatio;
}

// ═══════════════════════════════════════════════════════════════════════════
// RISK ENTRY DETECTION (Handbook P14)
// "Entering within the corrective pattern before break confirmation"
// Higher risk/reward — smaller stop = bigger R:R
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsRiskEntryLong()
{
   // Must be at/near support
   if(!FalconFX_NearSupport()) return false;
   
   // Must be in corrective nature (not impulsive)
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   
   // Must have bullish structure
   if(!g_bullishStructure) return false;
   
   // Must have confirmation candle
   bool hasPattern = false;
   if(InpUseEngulfing && FalconFX_BullishEngulfing(0)) hasPattern = true;
   if(InpUsePinBar && FalconFX_BullishPinBar(0))    hasPattern = true;
   
   return hasPattern;
}

bool FalconFX_IsRiskEntryShort()
{
   if(!FalconFX_NearResistance()) return false;
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   if(!g_bearishStructure) return false;
   
   bool hasPattern = false;
   if(InpUseEngulfing && FalconFX_BearishEngulfing(0)) hasPattern = true;
   if(InpUsePinBar && FalconFX_BearishPinBar(0))    hasPattern = true;
   
   return hasPattern;
}

// ═══════════════════════════════════════════════════════════════════════════
// REDUCED RISK ENTRY DETECTION (Handbook P15)
// "Entering once our continuation pattern has been broken and thus confirmed"
// Higher strike rate, slightly less R:R
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsReducedRiskEntryLong()
{
   if(!g_bullishStructure) return false;
   
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double prevClose = iClose(_Symbol, PERIOD_CURRENT, 1);
   
   // Close above recent swing high = break confirmation
   bool breakAbove = (close > g_swingHighs[1]) && (prevClose <= g_swingHighs[1]);
   
   // Was in correction before break
   if(breakAbove && g_inCorrectivePhase)
      return true;
   
   return false;
}

bool FalconFX_IsReducedRiskEntryShort()
{
   if(!g_bearishStructure) return false;
   
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double prevClose = iClose(_Symbol, PERIOD_CURRENT, 1);
   
   bool breakBelow = (close < g_swingLows[1]) && (prevClose >= g_swingLows[1]);
   
   if(breakBelow && g_inCorrectivePhase)
      return true;
   
   return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// PATTERN WITHIN PATTERN CHECK (Falcon Quick Tips Ep2)
// "Pattern within a pattern always increases our probability"
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_PatternWithinPatternLong()
{
   return (FalconFX_NearSupport() && g_inCorrectivePhase &&
           (FalconFX_BullishEngulfing(0) || FalconFX_BullishPinBar(0) || FalconFX_IsInsideBar(0)));
}

bool FalconFX_PatternWithinPatternShort()
{
   return (FalconFX_NearResistance() && g_inCorrectivePhase &&
           (FalconFX_BearishEngulfing(0) || FalconFX_BearishPinBar(0) || FalconFX_IsInsideBar(0)));
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY SIGNAL DEDUPLICATION
// Prevent multiple signals on the same bar
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_NewSignal(bool currentSignal, bool &lastSignal)
{
   bool isNew = currentSignal && !lastSignal;
   lastSignal = currentSignal;
   return isNew;
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN TICK FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

void OnTick()
{
   // Update all analysis on new bar
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   
   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      
      // Update analysis
      FalconFX_UpdateNature();
      FalconFX_UpdateStructure();
   }
   
   // Manage existing positions on every tick
   FalconFX_ManageOpenPositions();
   
   // Only look for entries if we don't have a position
   if(FalconFX_HasOpenPosition())
      return;
   
   // Check session filter
   if(!FalconFX_InSession())
      return;
   
   // Check daily trade limit
   if(!FalconFX_CanTrade())
      return;
   
   // ─── LONG ENTRY CHECK ───
   bool riskEntryLong       = FalconFX_IsRiskEntryLong();
   bool reducedRiskEntryLong = FalconFX_IsReducedRiskEntryLong();
   bool patternWithinLong   = FalconFX_PatternWithinPatternLong();
   bool longSignal          = riskEntryLong || reducedRiskEntryLong || patternWithinLong;
   
   if(FalconFX_NewSignal(longSignal, g_lastSignalLong))
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = FalconFX_CalculateLongSL();
      double tp  = FalconFX_CalculateLongTP(ask, sl);
      
      string comment = riskEntryLong ? "FalconFX Risk Long" : 
                       reducedRiskEntryLong ? "FalconFX Reduced Long" : "FalconFX Pattern Long";
      
      if(FalconFX_OpenPosition(true, sl, tp))
         Print("FalconFX: LONG SIGNAL @ ", ask, " SL: ", sl, " TP: ", tp);
   }
   
   // ─── SHORT ENTRY CHECK ───
   bool riskEntryShort       = FalconFX_IsRiskEntryShort();
   bool reducedRiskEntryShort = FalconFX_IsReducedRiskEntryShort();
   bool patternWithinShort   = FalconFX_PatternWithinPatternShort();
   bool shortSignal          = riskEntryShort || reducedRiskEntryShort || patternWithinShort;
   
   if(FalconFX_NewSignal(shortSignal, g_lastSignalShort))
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = FalconFX_CalculateShortSL();
      double tp  = FalconFX_CalculateShortTP(bid, sl);
      
      string comment = riskEntryShort ? "FalconFX Risk Short" : 
                       reducedRiskEntryShort ? "FalconFX Reduced Short" : "FalconFX Pattern Short";
      
      if(FalconFX_OpenPosition(false, sl, tp))
         Print("FalconFX: SHORT SIGNAL @ ", bid, " SL: ", sl, " TP: ", tp);
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// ON TESTER — Called after backtest completes
// Returns custom optimization criterion (higher = better)
// ═══════════════════════════════════════════════════════════════════════════

double OnTester()
{
   double profit = TesterStatistics(STAT_PROFIT);
   double trades = TesterStatistics(STAT_TRADES);
   double pf     = TesterStatistics(STAT_PROFIT_FACTOR);
   double dd     = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   double winRate = 0;
   
   if(trades > 0)
   {
      double wins = TesterStatistics(STAT_PROFIT_TRADES);
      winRate = (wins / trades) * 100.0;
   }
   
   Print("══════════════════════════════════════════");
   Print("  FalconFX Bot v3.0 — Backtest Results");
   Print("══════════════════════════════════════════");
   Print("  Total Profit: ", profit);
   Print("  Total Trades: ", trades);
   Print("  Win Rate: ", winRate, "%");
   Print("  Profit Factor: ", pf);
   Print("  Max Drawdown: ", dd, "%");
   Print("══════════════════════════════════════════");
   
   // Custom criterion: profit * win_rate / drawdown (risk-adjusted)
   if(dd > 0)
      return (profit * winRate) / dd;
   
   return profit;
}
