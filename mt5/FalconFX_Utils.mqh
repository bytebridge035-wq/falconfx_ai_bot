// ============================================================================
// FalconFX_Utils.mqh — Utility Functions for MT5
// FalconFX Strategy Handbook Implementation
// 
// Contains: Swing Detection, Nature Theory, Structure Analysis, 
//           Candlestick Patterns, S/R Zones, 90% Rule
// ============================================================================

#ifndef FALCONFX_UTILS_MQH
#define FALCONFX_UTILS_MQH

#include <Trade\Trade.mqh>

// ═══════════════════════════════════════════════════════════════════════════
// INPUT PARAMETERS
// ═══════════════════════════════════════════════════════════════════════════

input group "═══ NATURE THEORY & STRUCTURE ═══"
input int    InpSwingLookback      = 10;    // Swing Lookback (bars each side). Optimized: 10
input int    InpStructureLookback  = 50;    // Structure HTF Lookback
input int    InpImpulseMinBars     = 3;     // Min consecutive bars for impulse
input int    InpATRPeriod          = 14;    // ATR Period
input double InpSLBufferATR        = 1.5;   // SL Buffer beyond structure (x ATR). Optimized: 1.5

input group "═══ PATTERN DETECTION ═══"
input bool   InpUseEngulfing       = true;  // Engulfing at Structure
input bool   InpUsePinBar          = true;  // Pin Bars at Structure
input bool   InpUseInsideBar       = true;  // Inside Bar (Multi-Touch)
input bool   InpUse90Percent       = true;  // 90% Rule Reversal Watch

input group "═══ SESSION FILTER ═══"
input bool   InpUseSessionFilter   = true;  // Filter by Session
input int    InpLondonStart        = 7;     // London Open (UTC hour)
input int    InpLondonEnd          = 16;    // London Close (UTC hour)
input int    InpNYStart            = 12;    // NY Open (UTC hour)
input int    InpNYEnd              = 21;    // NY Close (UTC hour)

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════════════════

// Swing point storage
double g_swingHighs[3];    // Last 3 swing highs
double g_swingLows[3];     // Last 3 swing lows
int    g_swingHighBars[3]; // Bar indices of swing highs
int    g_swingLowBars[3];  // Bar indices of swing lows
int    g_swingHighCount = 0;
int    g_swingLowCount  = 0;

// Nature state
bool   g_inImpulsivePhase  = false;
bool   g_inCorrectivePhase = false;
int    g_consecutiveUp     = 0;
int    g_consecutiveDown   = 0;
int    g_impulseStartBar   = 0;

// 90% Rule tracking
double g_correctionStart    = 0.0;
double g_impulseTarget     = 0.0;
bool   g_tracking90Percent = false;

// Structure state
bool   g_bullishStructure  = false;
bool   g_bearishStructure  = false;

// S/R Levels
double g_resistanceLevel   = 0.0;
double g_supportLevel      = 0.0;

// ATR handle
int    g_atrHandle         = INVALID_HANDLE;

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_Init()
{
   // Create ATR indicator handle
   g_atrHandle = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   if(g_atrHandle == INVALID_HANDLE)
   {
      Print("FalconFX Error: Failed to create ATR indicator handle");
      return false;
   }
   
   // Initialize swing arrays
   ArrayInitialize(g_swingHighs, 0.0);
   ArrayInitialize(g_swingLows, 0.0);
   ArrayInitialize(g_swingHighBars, 0);
   ArrayInitialize(g_swingLowBars, 0);
   
   Print("FalconFX Utils initialized successfully");
   return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// CLEANUP
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_Deinit()
{
   if(g_atrHandle != INVALID_HANDLE)
   {
      IndicatorRelease(g_atrHandle);
      g_atrHandle = INVALID_HANDLE;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// ATR VALUE GETTER
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_GetATR(int shift = 0)
{
   double atr[];
   if(CopyBuffer(g_atrHandle, 0, shift, 1, atr) != 1)
      return 0.0;
   return atr[0];
}

// ═══════════════════════════════════════════════════════════════════════════
// SIMPLE MOVING AVERAGE
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_SMA(int period, int shift = 0)
{
   int handle = iMA(_Symbol, PERIOD_CURRENT, period, 0, MODE_SMA, PRICE_CLOSE);
   if(handle == INVALID_HANDLE) return 0.0;
   
   double sma[];
   if(CopyBuffer(handle, 0, shift, 1, sma) != 1)
   {
      IndicatorRelease(handle);
      return 0.0;
   }
   
   IndicatorRelease(handle);
   return sma[0];
}

// ═══════════════════════════════════════════════════════════════════════════
// HIGHEST / LOWEST OVER RANGE
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_Highest(int lookback, int shift = 0)
{
   double highest = 0;
   for(int i = shift; i < shift + lookback; i++)
   {
      double h = iHigh(_Symbol, PERIOD_CURRENT, i);
      if(h > highest) highest = h;
   }
   return highest;
}

double FalconFX_Lowest(int lookback, int shift = 0)
{
   double lowest = DBL_MAX;
   for(int i = shift; i < shift + lookback; i++)
   {
      double l = iLow(_Symbol, PERIOD_CURRENT, i);
      if(l < lowest) lowest = l;
   }
   return lowest;
}

// ═══════════════════════════════════════════════════════════════════════════
// SWING DETECTION (Equivalent to Pine Script ta.pivothigh/pivotlow)
// "Identifying large outer structures; identifying trends"
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsSwingHigh(int bar, int lookback)
{
   double high = iHigh(_Symbol, PERIOD_CURRENT, bar);
   
   for(int i = bar - lookback; i <= bar + lookback; i++)
   {
      if(i == bar) continue;
      if(i < 0 || i >= iBars(_Symbol, PERIOD_CURRENT)) continue;
      if(iHigh(_Symbol, PERIOD_CURRENT, i) >= high)
         return false;
   }
   return true;
}

bool FalconFX_IsSwingLow(int bar, int lookback)
{
   double low = iLow(_Symbol, PERIOD_CURRENT, bar);
   
   for(int i = bar - lookback; i <= bar + lookback; i++)
   {
      if(i == bar) continue;
      if(i < 0 || i >= iBars(_Symbol, PERIOD_CURRENT)) continue;
      if(iLow(_Symbol, PERIOD_CURRENT, i) <= low)
         return false;
   }
   return true;
}

void FalconFX_UpdateSwingPoints()
{
   int bars = iBars(_Symbol, PERIOD_CURRENT);
   if(bars < InpSwingLookback * 2 + 1) return;
   
   // Check for swing high at the bar that's 'lookback' bars ago
   int checkBar = bars - InpSwingLookback - 1;
   if(checkBar >= InpSwingLookback && FalconFX_IsSwingHigh(checkBar, InpSwingLookback))
   {
      // Shift array
      g_swingHighs[2] = g_swingHighs[1];
      g_swingHighs[1] = g_swingHighs[0];
      g_swingHighs[0] = iHigh(_Symbol, PERIOD_CURRENT, checkBar);
      g_swingHighBars[2] = g_swingHighBars[1];
      g_swingHighBars[1] = g_swingHighBars[0];
      g_swingHighBars[0] = checkBar;
      if(g_swingHighCount < 3) g_swingHighCount++;
   }
   
   // Check for swing low
   if(checkBar >= InpSwingLookback && FalconFX_IsSwingLow(checkBar, InpSwingLookback))
   {
      g_swingLows[2] = g_swingLows[1];
      g_swingLows[1] = g_swingLows[0];
      g_swingLows[0] = iLow(_Symbol, PERIOD_CURRENT, checkBar);
      g_swingLowBars[2] = g_swingLowBars[1];
      g_swingLowBars[1] = g_swingLowBars[0];
      g_swingLowBars[0] = checkBar;
      if(g_swingLowCount < 3) g_swingLowCount++;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// NATURE THEORY — IMPULSIVE vs CORRECTIVE (Handbook P7-9)
// 
// "Nature theory is the foundation — impulsive phases and corrective phases
// form the breathing cycle of the market (1-2-3: Impulse-Correction-Impulse)"
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateNature()
{
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double open  = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double high  = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low   = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   double bodySize = MathAbs(close - open);
   double range    = high - low;
   
   // Calculate average body and range over 20 bars
   double avgBody = 0, avgRange = 0;
   for(int i = 0; i < 20; i++)
   {
      avgBody += MathAbs(iClose(_Symbol, PERIOD_CURRENT, i) - iOpen(_Symbol, PERIOD_CURRENT, i));
      avgRange += iHigh(_Symbol, PERIOD_CURRENT, i) - iLow(_Symbol, PERIOD_CURRENT, i);
   }
   avgBody /= 20.0;
   avgRange /= 20.0;
   
   // Count consecutive directional bars
   bool upBar   = close > open;
   bool downBar = close < open;
   
   if(upBar)
   {
      g_consecutiveUp++;
      g_consecutiveDown = 0;
   }
   else if(downBar)
   {
      g_consecutiveDown++;
      g_consecutiveUp = 0;
   }
   else
   {
      g_consecutiveUp   = 0;
      g_consecutiveDown = 0;
   }
   
   // Impulse detection: consecutive directional bars with large bodies
   bool impulseUp   = (g_consecutiveUp >= InpImpulseMinBars) && (bodySize > avgBody * 1.3);
   bool impulseDown = (g_consecutiveDown >= InpImpulseMinBars) && (bodySize > avgBody * 1.3);
   
   // Corrective detection: small bodies, tight range
   bool isCorrective = (bodySize < avgBody * 0.6) && (range < avgRange * 0.7) &&
                       (MathAbs(close - open) < MathAbs(high - low) * 0.4);
   
   // Phase transitions
   if(impulseUp || impulseDown)
   {
      g_inImpulsivePhase  = true;
      g_inCorrectivePhase = false;
      g_impulseStartBar   = 0;
      
      // Start tracking 90% rule
      g_correctionStart = close;
      g_tracking90Percent = true;
   }
   else if(g_inImpulsivePhase && isCorrective)
   {
      g_inImpulsivePhase  = false;
      g_inCorrectivePhase = true;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// MARKET STRUCTURE — The Breathing Cycle (Handbook P10-12)
// "Bullish: Higher Highs + Higher Lows"
// "Bearish: Lower Highs + Lower Lows"
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateStructure()
{
   FalconFX_UpdateSwingPoints();
   
   if(g_swingHighCount >= 2 && g_swingLowCount >= 2)
   {
      g_bullishStructure = (g_swingHighs[0] > g_swingHighs[1]) && 
                           (g_swingLows[0] > g_swingLows[1]);
      g_bearishStructure = (g_swingHighs[0] < g_swingHighs[1]) && 
                           (g_swingLows[0] < g_swingLows[1]);
   }
   
   // Update S/R levels
   if(g_swingHighCount > 0)
      g_resistanceLevel = g_swingHighs[0];
   else
      g_resistanceLevel = FalconFX_Highest(InpStructureLookback);
   
   if(g_swingLowCount > 0)
      g_supportLevel = g_swingLows[0];
   else
      g_supportLevel = FalconFX_Lowest(InpStructureLookback);
}

// ═══════════════════════════════════════════════════════════════════════════
// SUPPORT & RESISTANCE PROXIMITY (Handbook P12)
// "How price approaches the edges of structure"
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_NearResistance()
{
   double atr = FalconFX_GetATR(0);
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double zoneSize = atr * 0.5;
   return (MathAbs(close - g_resistanceLevel) < zoneSize);
}

bool FalconFX_NearSupport()
{
   double atr = FalconFX_GetATR(0);
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double zoneSize = atr * 0.5;
   return (MathAbs(close - g_supportLevel) < zoneSize);
}

bool FalconFX_AtResistance()
{
   double atr = FalconFX_GetATR(0);
   double high = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double zoneSize = atr * 0.5;
   return (high >= g_resistanceLevel - zoneSize * 0.3 && 
           high <= g_resistanceLevel + zoneSize);
}

bool FalconFX_AtSupport()
{
   double atr = FalconFX_GetATR(0);
   double low = iLow(_Symbol, PERIOD_CURRENT, 0);
   double zoneSize = atr * 0.5;
   return (low <= g_supportLevel + zoneSize * 0.3 && 
           low >= g_supportLevel - zoneSize);
}

// ═══════════════════════════════════════════════════════════════════════════
// CANDLESTICK PATTERNS (Handbook P8, Falcon Quick Tips)
// "We are outlining PROBABLE turning points — perfect patterns are not what 
// we are searching for"
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_BullishEngulfing(int shift = 0)
{
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   double open  = iOpen(_Symbol, PERIOD_CURRENT, shift);
   double prevClose = iClose(_Symbol, PERIOD_CURRENT, shift + 1);
   double prevOpen  = iOpen(_Symbol, PERIOD_CURRENT, shift + 1);
   
   double bodySize = MathAbs(close - open);
   double prevBody = MathAbs(prevClose - prevOpen);
   
   // Engulfing: current candle fully engulfs previous candle.
   // Aligned with Pine Script: strict < and > (no >=, no 1.2x body filter).
   return (close > open && prevClose < prevOpen &&
           open < prevClose && close > prevOpen);
}

bool FalconFX_BearishEngulfing(int shift = 0)
{
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   double open  = iOpen(_Symbol, PERIOD_CURRENT, shift);
   double prevClose = iClose(_Symbol, PERIOD_CURRENT, shift + 1);
   double prevOpen  = iOpen(_Symbol, PERIOD_CURRENT, shift + 1);
   
   double bodySize = MathAbs(close - open);
   double prevBody = MathAbs(prevClose - prevOpen);
   
   return (close < open && prevClose > prevOpen &&
           open > prevClose && close < prevOpen);
}

bool FalconFX_BullishPinBar(int shift = 0)
{
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   double open  = iOpen(_Symbol, PERIOD_CURRENT, shift);
   double high  = iHigh(_Symbol, PERIOD_CURRENT, shift);
   double low   = iLow(_Symbol, PERIOD_CURRENT, shift);
   
   double bodySize = MathAbs(close - open);
   double range    = high - low;
   double upperWick = high - MathMax(close, open);
   double lowerWick = MathMin(close, open) - low;
   
   // Average range over 20 bars
   double avgRange = 0;
   for(int i = shift; i < shift + 20; i++)
      avgRange += iHigh(_Symbol, PERIOD_CURRENT, i) - iLow(_Symbol, PERIOD_CURRENT, i);
   avgRange /= 20.0;
   
   // Pin bar ratios aligned with Pine Script v6:
   // Bull: lowerWick > bodySize * 2.0, upperWick < bodySize * 0.5
   return (lowerWick > bodySize * 2.0 && upperWick < bodySize * 0.3 &&
           range > avgRange * 0.6 && close > open);
}

bool FalconFX_BearishPinBar(int shift = 0)
{
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   double open  = iOpen(_Symbol, PERIOD_CURRENT, shift);
   double high  = iHigh(_Symbol, PERIOD_CURRENT, shift);
   double low   = iLow(_Symbol, PERIOD_CURRENT, shift);
   
   double bodySize = MathAbs(close - open);
   double range    = high - low;
   double upperWick = high - MathMax(close, open);
   double lowerWick = MathMin(close, open) - low;
   
   double avgRange = 0;
   for(int i = shift; i < shift + 20; i++)
      avgRange += iHigh(_Symbol, PERIOD_CURRENT, i) - iLow(_Symbol, PERIOD_CURRENT, i);
   avgRange /= 20.0;
   
   // Bear: upperWick > bodySize * 2.0, lowerWick < bodySize * 0.5
   return (upperWick > bodySize * 2.0 && lowerWick < bodySize * 0.3 &&
           range > avgRange * 0.6 && close < open);
}

bool FalconFX_IsInsideBar(int shift = 0)
{
   double high = iHigh(_Symbol, PERIOD_CURRENT, shift);
   double low  = iLow(_Symbol, PERIOD_CURRENT, shift);
   double prevHigh = iHigh(_Symbol, PERIOD_CURRENT, shift + 1);
   double prevLow  = iLow(_Symbol, PERIOD_CURRENT, shift + 1);
   
   return (high < prevHigh && low > prevLow);
}

// ═══════════════════════════════════════════════════════════════════════════
// 90% RULE (Handbook P22)
// "90% of the time an impulsive move should reach the start of the 
// correction of the pattern of which you are trading"
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_Get90PercentLevel()
{
   return g_correctionStart;
}

bool FalconFX_Approaching90Percent()
{
   if(!InpUse90Percent || !g_tracking90Percent || g_correctionStart == 0.0)
      return false;
   
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double atr  = FalconFX_GetATR(0);
   double distTo90 = MathAbs(close - g_correctionStart);
   
   return (distTo90 < atr * 0.5);
}

// ═══════════════════════════════════════════════════════════════════════════
// SESSION FILTER
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_InSession()
{
   if(!InpUseSessionFilter) return true;
   
   MqlDateTime dt;
   TimeCurrent(dt);
   int currentHour = dt.hour;
   
   bool inLondon = (currentHour >= InpLondonStart && currentHour < InpLondonEnd);
   bool inNY     = (currentHour >= InpNYStart && currentHour < InpNYEnd);
   
   return (inLondon || inNY);
}

// ═══════════════════════════════════════════════════════════════════════════
// STRUCTURE CHANGE DETECTION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_StructureFlipBullish()
{
   static bool prevBullish = false;
   bool result = g_bullishStructure && !prevBullish;
   prevBullish = g_bullishStructure;
   return result;
}

bool FalconFX_StructureFlipBearish()
{
   static bool prevBearish = false;
   bool result = g_bearishStructure && !prevBearish;
   prevBearish = g_bearishStructure;
   return result;
}

#endif // FALCONFX_UTILS_MQH
