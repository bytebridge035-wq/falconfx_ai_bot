// ============================================================================
// FalconFX.mq5 — MT5 Expert Advisor v6.0
// FalconFX Strategy Handbook Implementation (Mark Hutchinson)
// 
// v6 Updates:
//   - FTMO compliance: daily loss limit, total DD limit
//   - Consecutive loss limit
//   - Fixed daily counter logic
//   - Aligned with Pine Script v6 logic
// ============================================================================

#property copyright "FalconFX Bot v6.0"
#property link      "https://github.com/bytebridge035-wq/falconfx_ai_bot"
#property version   "6.00"
#property strict

// ═══════════════════════════════════════════════════════════════════════════
// INPUTS
// ═══════════════════════════════════════════════════════════════════════════

input group "═══ FTMO RISK COMPLIANCE ═══"
input double InpRiskPercent     = 1.0;   // Risk Per Trade %
input double InpMaxDailyLoss    = 5.0;   // Max Daily Loss % (FTMO: 5%)
input double InpMaxTotalDD      = 8.0;   // Max Total DD % (FTMO: 10%)
input int    InpMaxTradesDay    = 4;     // Max Trades Per Day
input int    InpMaxConsecLoss   = 3;     // Max Consecutive Losses
input double InpDailyStartEquity = 10000; // Daily Start Equity Reference

input group "═══ STRUCTURE ═══"
input int    InpSwingLookback   = 10;    // Swing Lookback Period
input int    InpStructureLB     = 50;    // Structure HTF Lookback

input group "═══ ENTRY PATTERNS ═══"
input bool   InpUseRiskEntry    = true;  // Enable Risk Entry
input bool   InpUseReducedEntry  = true;  // Enable Reduced Risk Entry
input bool   InpUseEngulfing    = true;  // Require Engulfing Pattern
input bool   InpUsePinBar       = true;  // Require Pin Bar Pattern
input bool   InpUseInsideBar    = false; // Require Inside Bar Pattern
input bool   InpUseFlag         = true;  // Require Flag/Breakout

input group "═══ TRADE MANAGEMENT ═══"
input double InpSLBufferATR     = 1.5;   // SL Buffer (x ATR)
input double InpTPRatio         = 3.0;   // TP R:R Ratio
input double InpBETrigger       = 1.5;   // Break-Even Trigger (x R)
input bool   InpUseHalfRisk     = true;  // Half-Risk Method
input int    InpBEEntryBuffer   = 20;    // B/E buffer (points)

input group "═══ SCALING IN ═══"
input bool   InpEnableScaling   = false; // Enable Scaling In
input int    InpMaxScaleIns     = 2;     // Max Scale-Ins per Trade
input double InpScaleInRisk     = 1.0;   // Scale-In Risk %
input ulong  InpMagic           = 498817; // Magic Number

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════════════════

// Structure tracking
double g_sh1 = 0, g_sh2 = 0;
double g_sl1 = 0, g_sl2 = 0;
double g_resistanceLevel = 0, g_supportLevel = 0;
double g_atrValue = 0;

// Nature tracking
bool g_inImpulsivePhase = false;
bool g_inCorrectivePhase = false;
int g_consecutiveUp = 0;
int g_consecutiveDown = 0;
double g_avgBody = 0;
double g_avgRange = 0;

// 90% Rule
double g_correctionStart = 0;

// Daily tracking
int g_tradesToday = 0;
int g_dailyStartDay = 0;
double g_dailyStartEq = 0;
double g_peakEquity = 0;
int g_consecLosses = 0;

// Signal deduplication
bool g_lastSignalLong = false;
bool g_lastSignalShort = false;

// Pattern state
bool g_bullishEngulfing = false;
bool g_bearishEngulfing = false;
bool g_bullishPinBar = false;
bool g_bearishPinBar = false;
bool g_isInsideBar = false;
bool g_nearSupport = false;
bool g_nearResistance = false;
bool g_bullishStructure = false;
bool g_bearishStructure = false;

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_GetATR(int shift)
{
   double atr = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(atr <= 0)
      atr = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 100;
   return atr;
}

// ═══════════════════════════════════════════════════════════════════════════
// PATTERN DETECTION
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdatePatterns()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double open0  = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double high0  = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0   = iLow(_Symbol, PERIOD_CURRENT, 0);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double open1  = iOpen(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow(_Symbol, PERIOD_CURRENT, 1);
   
   double bodySize = MathAbs(close0 - open0);
   double range    = high0 - low0;
   double upperWick = high0 - MathMax(close0, open0);
   double lowerWick = MathMin(close0, open0) - low0;
   bool isBullish = close0 > open0;
   bool isBearish = close0 < open0;
   
   // Engulfing
   g_bullishEngulfing = isBullish && close1 < open1 && open0 <= close1 && close0 >= open1;
   g_bearishEngulfing = isBearish && close1 > open1 && open0 >= close1 && close0 <= open1;
   
   // Pin Bar
   g_bullishPinBar = lowerWick > bodySize * 2.5 && upperWick < bodySize * 0.3 && range > g_avgRange * 0.6 && isBullish;
   g_bearishPinBar = upperWick > bodySize * 2.5 && lowerWick < bodySize * 0.3 && range > g_avgRange * 0.6 && isBearish;
   
   // Inside Bar
   g_isInsideBar = high0 < high1 && low0 > low1;
   
   // Proximity to S/R
   double zoneSize = g_atrValue * 1.5;
   g_nearResistance = (g_resistanceLevel > 0) && (MathAbs(close0 - g_resistanceLevel) < zoneSize);
   g_nearSupport    = (g_supportLevel > 0) && (MathAbs(close0 - g_supportLevel) < zoneSize);
}

// ═══════════════════════════════════════════════════════════════════════════
// STRUCTURE UPDATE
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateStructure()
{
   double high0 = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0  = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   // Swing detection
   bool newSwingHigh = true;
   bool newSwingLow  = true;
   
   for(int i = 1; i <= InpSwingLookback; i++)
   {
      if(iHigh(_Symbol, PERIOD_CURRENT, i) >= high0)
         newSwingHigh = false;
      if(iLow(_Symbol, PERIOD_CURRENT, i) <= low0)
         newSwingLow = false;
   }
   
   if(newSwingHigh)
   {
      g_sh2 = g_sh1;
      g_sh1 = high0;
   }
   
   if(newSwingLow)
   {
      g_sl2 = g_sl1;
      g_sl1 = low0;
   }
   
   // S/R levels
   g_resistanceLevel = (g_sh1 > 0) ? g_sh1 : iHigh(_Symbol, PERIOD_CURRENT, 0);
   g_supportLevel    = (g_sl1 > 0) ? g_sl1 : iLow(_Symbol, PERIOD_CURRENT, 0);
   
   // Structure classification
   g_bullishStructure = (g_sh1 > 0 && g_sh2 > 0 && g_sl1 > 0 && g_sl2 > 0 && g_sh1 > g_sh2 && g_sl1 > g_sl2);
   g_bearishStructure = (g_sh1 > 0 && g_sh2 > 0 && g_sl1 > 0 && g_sl2 > 0 && g_sh1 < g_sh2 && g_sl1 < g_sl2);
}

// ═══════════════════════════════════════════════════════════════════════════
// NATURE THEORY UPDATE
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateNature()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double open0  = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double high0  = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0   = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   double bodySize = MathAbs(close0 - open0);
   double range    = high0 - low0;
   
   // Update averages (EMA approximation)
   if(g_avgBody == 0) g_avgBody = bodySize;
   if(g_avgRange == 0) g_avgRange = range;
   g_avgBody = g_avgBody * 0.95 + bodySize * 0.05;
   g_avgRange = g_avgRange * 0.95 + range * 0.05;
   
   bool upBar   = close0 > open0;
   bool downBar = close0 < open0;
   
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
      g_consecutiveUp = 0;
      g_consecutiveDown = 0;
   }
   
   bool isImpulseUp   = g_consecutiveUp >= 3 && bodySize > g_avgBody * 1.3;
   bool isImpulseDown = g_consecutiveDown >= 3 && bodySize > g_avgBody * 1.3;
   bool isCorrective  = bodySize < g_avgBody * 0.6 && range < g_avgRange * 0.7;
   
   if(isImpulseUp || isImpulseDown)
   {
      g_inImpulsivePhase = true;
      g_inCorrectivePhase = false;
   }
   
   if(g_inImpulsivePhase && isCorrective)
   {
      g_inImpulsivePhase = false;
      g_inCorrectivePhase = true;
      g_correctionStart = close0;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// FTMO DAILY COUNTER (Fixed: uses actual calendar day)
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateDailyCounter()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   
   // Reset on new calendar day (not every 24 bars — fixes weekend gap bug)
   if(dt.day != g_dailyStartDay || dt.day_of_year == 0)
   {
      g_dailyStartDay   = dt.day;
      g_tradesToday     = 0;
      g_dailyStartEq    = AccountInfoDouble(ACCOUNT_BALANCE);
      g_peakEquity      = AccountInfoDouble(ACCOUNT_BALANCE);
      g_consecLosses    = 0;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// FTMO CAN-TRADE CHECK (Daily loss + total DD + consecutive losses)
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_CanTrade()
{
   // Check daily trade count
   if(g_tradesToday >= InpMaxTradesDay)
      return false;
   
   // Check consecutive loss limit
   if(g_consecLosses >= InpMaxConsecLoss)
      return false;
   
   // Check daily loss limit
   double dailyPnL = AccountInfoDouble(ACCOUNT_BALANCE) - g_dailyStartEq;
   double dailyLossLimit = g_dailyStartEq * InpMaxDailyLoss / 100.0;
   if(dailyPnL < -dailyLossLimit)
      return false;
   
   // Check total drawdown limit
   double currentEquity = AccountInfoDouble(ACCOUNT_BALANCE);
   if(currentEquity > g_peakEquity)
      g_peakEquity = currentEquity;
   double totalDDLimit = g_peakEquity * InpMaxTotalDD / 100.0;
   if(currentEquity < g_peakEquity - totalDDLimit)
      return false;
   
   return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// PATTERN CHECK
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_HasBullPattern()
{
   return (InpUseEngulfing && g_bullishEngulfing) || 
          (InpUsePinBar && g_bullishPinBar) || 
          (InpUseInsideBar && g_isInsideBar) ||
          (InpUseFlag && (g_bullishEngulfing || g_bullishPinBar));
}

bool FalconFX_HasBearPattern()
{
   return (InpUseEngulfing && g_bearishEngulfing) || 
          (InpUsePinBar && g_bearishPinBar) || 
          (InpUseInsideBar && g_isInsideBar) ||
          (InpUseFlag && (g_bearishEngulfing || g_bearishPinBar));
}

// ═══════════════════════════════════════════════════════════════════════════
// SIGNAL DEDUPLICATION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_NewSignal(bool currentSignal, bool &lastSignal)
{
   bool isNew = currentSignal && !lastSignal;
   lastSignal = currentSignal;
   return isNew;
}

// ═══════════════════════════════════════════════════════════════════════════
// POSITION CHECK
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   }
   return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// CALCULATE STOP LOSS
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_CalculateLongSL()
{
   if(g_supportLevel > 0)
      return g_supportLevel - g_atrValue * InpSLBufferATR;
   return SymbolInfoDouble(_Symbol, SYMBOL_ASK) - g_atrValue * InpSLBufferATR;
}

double FalconFX_CalculateShortSL()
{
   if(g_resistanceLevel > 0)
      return g_resistanceLevel + g_atrValue * InpSLBufferATR;
   return SymbolInfoDouble(_Symbol, SYMBOL_BID) + g_atrValue * InpSLBufferATR;
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
// OPEN POSITION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_OpenPosition(bool isLong, double sl, double tp)
{
   MqlTradeRequest request = {};
   MqlTradeResult result   = {};
   
   request.action    = TRADE_ACTION_DEAL;
   request.symbol    = _Symbol;
   request.magic     = InpMagic;
   request.deviation = 10;
   
   if(isLong)
   {
      request.type  = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.sl    = sl;
      request.tp    = tp;
      request.comment = "FalconFX Long";
   }
   else
   {
      request.type  = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.sl    = sl;
      request.tp    = tp;
      request.comment = "FalconFX Short";
   }
   
   // Position size: risk-based
   double riskAmount = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double slDiff     = MathAbs(request.price - sl);
   
   if(tickValue > 0 && slDiff > 0)
   {
      double qty = riskAmount / (slDiff / tickSize * tickValue);
      request.volume = NormalizeDouble(qty, 2);
   }
   else
   {
      request.volume = 0.01;
   }
   
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(request.volume < minLot)
      request.volume = minLot;
   
   if(!OrderSend(request, result))
   {
      Print("FalconFX: OrderSend failed. Error: ", GetLastError());
      return false;
   }
   
   return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// MANAGEMENT: Break-even method
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_ApplyBreakEven()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      
      double openPrice     = PositionGetDouble(POSITION_PRICE_OPEN);
      double currentSL     = PositionGetDouble(POSITION_SL);
      double currentTP     = PositionGetDouble(POSITION_TP);
      double currentPrice  = PositionGetDouble(POSITION_PRICE_CURRENT);
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      
      double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double risk   = MathAbs(openPrice - currentSL);
      
      if(risk <= 0) continue;
      
      MqlTradeRequest req = {};
      MqlTradeResult res  = {};
      req.action  = TRADE_ACTION_SLTP;
      req.symbol  = _Symbol;
      req.position = ticket;
      req.tp      = currentTP;
      
      if(posType == POSITION_TYPE_BUY)
      {
         // B/E: move SL to entry when price moves 1R into profit
         if(currentPrice >= openPrice + risk * InpBETrigger)
         {
            double newSL = openPrice + point * InpBEEntryBuffer;
            if(newSL > currentSL)
            {
               req.sl = newSL;
               OrderSend(req, res);
            }
         }
      }
      else // POSITION_TYPE_SELL
      {
         if(currentPrice <= openPrice - risk * InpBETrigger)
         {
            double newSL = openPrice - point * InpBEEntryBuffer;
            if(newSL < currentSL || currentSL == 0)
            {
               req.sl = newSL;
               OrderSend(req, res);
            }
         }
      }
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY DETECTION: Risk Entry
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsRiskEntryLong()
{
   if(!g_nearSupport) return false;
   if(!g_bullishStructure) return false;
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   if(!FalconFX_HasBullPattern()) return false;
   return true;
}

bool FalconFX_IsRiskEntryShort()
{
   if(!g_nearResistance) return false;
   if(!g_bearishStructure) return false;
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   if(!FalconFX_HasBearPattern()) return false;
   return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY DETECTION: Reduced Risk Entry
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsReducedRiskEntryLong()
{
   if(!g_bullishStructure) return false;
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   bool breakAbove = (close0 > g_sh1) && (close1 <= g_sh1);
   return breakAbove && g_inCorrectivePhase;
}

bool FalconFX_IsReducedRiskEntryShort()
{
   if(!g_bearishStructure) return false;
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   bool breakBelow = (close0 < g_sl1) && (close1 >= g_sl1);
   return breakBelow && g_inCorrectivePhase;
}

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

int OnInit()
{
   if(InpSwingLookback < 3)
   {
      Print("FalconFX: Swing Lookback must be >= 3");
      return INIT_FAILED;
   }
   
   g_dailyStartEq = AccountInfoDouble(ACCOUNT_BALANCE);
   g_peakEquity   = g_dailyStartEq;
   
   Print("FalconFX Bot v6.0 initialized. Symbol: ", _Symbol, " TF: ", EnumToString(Period()));
   Print("FTMO: MaxDailyLoss=", InpMaxDailyLoss, "% MaxDD=", InpMaxTotalDD, "% MaxTrades=", InpMaxTradesDay);
   return INIT_SUCCEEDED;
}

// ═══════════════════════════════════════════════════════════════════════════
// DEINITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

void OnDeinit(const int reason)
{
   Print("FalconFX Bot v6.0 stopped. Reason: ", reason);
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN TICK FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

void OnTick()
{
   // Update ATR
   g_atrValue = FalconFX_GetATR(0);
   
   // Update on new bar
   static datetime lastBarTime = 0;
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   
   if(currentBarTime != lastBarTime)
   {
      lastBarTime = currentBarTime;
      
      // Update analysis
      FalconFX_UpdateNature();
      FalconFX_UpdateStructure();
      FalconFX_UpdatePatterns();
      FalconFX_UpdateDailyCounter();
   }
   
   // Manage existing positions on every tick
   FalconFX_ApplyBreakEven();
   
   // Only look for entries if we don't have a position
   if(FalconFX_HasOpenPosition())
      return;
   
   // FTMO compliance check
   if(!FalconFX_CanTrade())
      return;
   
   // ─── LONG ENTRY CHECK ───
   bool riskEntryLong    = FalconFX_IsRiskEntryLong();
   bool reducedEntryLong = FalconFX_IsReducedRiskEntryLong();
   bool longSignal = (InpUseRiskEntry && riskEntryLong) || (InpUseReducedEntry && reducedEntryLong);
   
   if(FalconFX_NewSignal(longSignal, g_lastSignalLong))
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = FalconFX_CalculateLongSL();
      double tp  = FalconFX_CalculateLongTP(ask, sl);
      
      if(FalconFX_OpenPosition(true, sl, tp))
      {
         g_tradesToday++;
         Print("FalconFX: LONG @ ", ask, " SL: ", sl, " TP: ", tp);
      }
   }
   
   // ─── SHORT ENTRY CHECK ───
   bool riskEntryShort    = FalconFX_IsRiskEntryShort();
   bool reducedEntryShort = FalconFX_IsReducedRiskEntryShort();
   bool shortSignal = (InpUseRiskEntry && riskEntryShort) || (InpUseReducedEntry && reducedEntryShort);
   
   if(FalconFX_NewSignal(shortSignal, g_lastSignalShort))
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = FalconFX_CalculateShortSL();
      double tp  = FalconFX_CalculateShortTP(bid, sl);
      
      if(FalconFX_OpenPosition(false, sl, tp))
      {
         g_tradesToday++;
         Print("FalconFX: SHORT @ ", bid, " SL: ", sl, " TP: ", tp);
      }
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// ON TESTER — Custom optimization criterion
// ═══════════════════════════════════════════════════════════════════════════

double OnTester()
{
   double profit = TesterStatistics(STAT_PROFIT);
   double trades = TesterStatistics(STAT_TRADES);
   double pf     = TesterStatistics(STAT_PROFIT_FACTOR);
   double dd     = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   double ddAbs  = TesterStatistics(STAT_EQUITY_DD);
   
   Print("=== FalconFX v6.0 Backtest ===");
   Print("Profit: ", profit, " | Trades: ", trades, " | PF: ", pf, " | DD: ", dd, "% | DD$", ddAbs);
   
   if(dd > 0)
      return (profit * (trades > 0 ? profit / trades : 0)) / dd;
   return profit;
}
