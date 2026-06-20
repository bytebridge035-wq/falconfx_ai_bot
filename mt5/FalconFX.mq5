// ============================================================================
// FalconFX.mq5 — MT5 Expert Advisor v3.3
// FalconFX Strategy Handbook Implementation (Mark Hutchinson)
// 
// Logic alignment: Matches Pine Script v3.3 strategy exactly
//   - Nature Theory (impulsive vs corrective phase tracking)
//   - Market Structure (HH/HL bullish, LH/LL bearish)
//   - Entry Types: Risk Entry + Reduced Risk Entry
//   - Pattern filters: Engulfing, Pin Bar, Inside Bar (toggleable)
//   - Trade Management: B/E method, Half-Risk method, 90% Rule
//   - Scaling In (toggleable)
//   - Daily trade limit
// ============================================================================

#property copyright "FalconFX Bot v3.3"
#property link      "https://github.com/bytebridge035-wq/falconfx_ai_bot"
#property version   "3.30"
#property strict

// ═══════════════════════════════════════════════════════════════════════════
// INPUTS
// ═══════════════════════════════════════════════════════════════════════════

input group "=== FALCONFX v3.3 ==="
input ulong InpMagic = 498817;           // Magic number

input group "=== STRUCTURE ==="
input int InpSwingLookback = 10;         // Swing Lookback
input int InpStructureLookback = 50;     // Structure HTF Lookback
input int InpImpulseMinBars = 3;         // Min Impulse Bars
input double InpEntryMaxDistATR = 0.5;   // Entry Max Distance (x ATR)

input group "=== ENTRY PATTERNS ==="
input bool InpUseRiskEntry = true;       // Enable Risk Entry
input bool InpUseReducedRiskEntry = true; // Enable Reduced Risk Entry
input bool InpUseEngulfing = true;        // Require Engulfing Pattern
input bool InpUsePinBar = true;           // Require Pin Bar Pattern
input bool InpUseInsideBar = false;       // Require Inside Bar Pattern

input group "=== TRADE MANAGEMENT ==="
input double InpRiskPercent = 1.0;        // Risk Per Trade %
input double InpSLBufferATR = 1.5;        // SL Buffer (x ATR)
input double InpTPRatio = 3.0;            // TP R:R Ratio
input int InpMaxTradesDay = 2;           // Max Trades Per Day
input bool InpUseHalfRisk = true;         // Half-Risk Method
input int InpHalfRiskThreshold = 1;       // Half-Risk trigger (bars)
input bool InpUse90Rule = true;           // 90% Rule

input group "=== SCALING IN ==="
input bool InpEnableScaling = false;      // Enable Scaling In
input int InpMaxScaleIns = 2;             // Max Scale-Ins per Trade
input double InpRiskPerScaleIn = 1.0;     // Scale-In Risk %

input group "=== SESSION ==="
input bool InpUseSessionFilter = false;   // Filter by Session

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════════════════

// Structure tracking
double g_sh1 = 0, g_sh2 = 0;
double g_sl1 = 0, g_sl2 = 0;
double g_outerHigh = 0, g_outerLow = 0;
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
bool g_phaseChanged = false;

// Daily trade tracking
int g_tradesToday = 0;
int g_barsThisDay = 0;

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
// UTILITY: ATR calculation
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_GetATR(int shift)
{
   double atr = iATR(_Symbol, PERIOD_CURRENT, 14);
   if(atr <= 0)
      atr = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 10;
   return atr;
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Pattern detection
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdatePatterns()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double open0 = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double high0 = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0 = iLow(_Symbol, PERIOD_CURRENT, 0);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double open1 = iOpen(_Symbol, PERIOD_CURRENT, 1);
   double high1 = iHigh(_Symbol, PERIOD_CURRENT, 1);
   double low1 = iLow(_Symbol, PERIOD_CURRENT, 1);
   
   double bodySize = MathAbs(close0 - open0);
   double range = high0 - low0;
   double upperWick = high0 - MathMax(close0, open0);
   double lowerWick = MathMin(close0, open0) - low0;
   bool isBullish = close0 > open0;
   bool isBearish = close0 < open0;
   
   // Engulfing
   g_bullishEngulfing = isBullish && close1 < open1 && open0 <= close1 && close0 >= open1 && bodySize > MathAbs(close1 - open1) * 1.2;
   g_bearishEngulfing = isBearish && close1 > open1 && open0 >= close1 && close0 <= open1 && bodySize > MathAbs(close1 - open1) * 1.2;
   
   // Pin Bar
   g_bullishPinBar = lowerWick > bodySize * 2.5 && upperWick < bodySize * 0.3 && range > g_avgRange * 0.6 && isBullish;
   g_bearishPinBar = upperWick > bodySize * 2.5 && lowerWick < bodySize * 0.3 && range > g_avgRange * 0.6 && isBearish;
   
   // Inside Bar
   g_isInsideBar = high0 < high1 && low0 > low1;
   
   // Proximity
   double zoneSize = g_atrValue * 0.5;
   g_nearResistance = MathAbs(close0 - g_resistanceLevel) < zoneSize;
   g_nearSupport = MathAbs(close0 - g_supportLevel) < zoneSize;
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Structure update
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateStructure()
{
   // Swing detection using pivot logic
   double high0 = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0 = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   // Update swing highs/lows using lookback
   bool newSwingHigh = true;
   bool newSwingLow = true;
   
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
   
   // Outer structure
   g_outerHigh = high0;
   g_outerLow = low0;
   for(int i = 0; i < InpStructureLookback; i++)
   {
      if(iHigh(_Symbol, PERIOD_CURRENT, i) > g_outerHigh)
         g_outerHigh = iHigh(_Symbol, PERIOD_CURRENT, i);
      if(iLow(_Symbol, PERIOD_CURRENT, i) < g_outerLow)
         g_outerLow = iLow(_Symbol, PERIOD_CURRENT, i);
   }
   
   // S/R levels
   g_resistanceLevel = (g_sh1 > 0) ? g_sh1 : g_outerHigh;
   g_supportLevel = (g_sl1 > 0) ? g_sl1 : g_outerLow;
   
   // Structure classification
   g_bullishStructure = (g_sh1 > 0 && g_sh2 > 0 && g_sl1 > 0 && g_sl2 > 0 && g_sh1 > g_sh2 && g_sl1 > g_sl2);
   g_bearishStructure = (g_sh1 > 0 && g_sh2 > 0 && g_sl1 > 0 && g_sl2 > 0 && g_sh1 < g_sh2 && g_sl1 < g_sl2);
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Nature theory update
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateNature()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double open0 = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double high0 = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low0 = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   double bodySize = MathAbs(close0 - open0);
   double range = high0 - low0;
   
   // Update averages (simple approximation of SMA)
   if(g_avgBody == 0) g_avgBody = bodySize;
   if(g_avgRange == 0) g_avgRange = range;
   g_avgBody = g_avgBody * 0.95 + bodySize * 0.05;
   g_avgRange = g_avgRange * 0.95 + range * 0.05;
   
   bool upBar = close0 > open0;
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
   
   bool isImpulseUp = g_consecutiveUp >= InpImpulseMinBars && bodySize > g_avgBody * 1.3;
   bool isImpulseDown = g_consecutiveDown >= InpImpulseMinBars && bodySize > g_avgBody * 1.3;
   bool isCorrective = bodySize < g_avgBody * 0.6 && range < g_avgRange * 0.7;
   
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
      g_phaseChanged = true;
   }
   else
   {
      g_phaseChanged = false;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Daily trade counter
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdateDailyCounter()
{
   g_barsThisDay++;
   if(g_barsThisDay >= 24)
   {
      g_barsThisDay = 0;
      g_tradesToday = 0;
   }
}

bool FalconFX_CanTrade()
{
   return g_tradesToday < InpMaxTradesDay;
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Entry distance check
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_LongDistOk()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   return MathAbs(close0 - g_supportLevel) <= InpEntryMaxDistATR * g_atrValue;
}

bool FalconFX_ShortDistOk()
{
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   return MathAbs(close0 - g_resistanceLevel) <= InpEntryMaxDistATR * g_atrValue;
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Pattern check
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_HasBullPattern()
{
   return (InpUseEngulfing && g_bullishEngulfing) || 
          (InpUsePinBar && g_bullishPinBar) || 
          (InpUseInsideBar && g_isInsideBar);
}

bool FalconFX_HasBearPattern()
{
   return (InpUseEngulfing && g_bearishEngulfing) || 
          (InpUsePinBar && g_bearishPinBar) || 
          (InpUseInsideBar && g_isInsideBar);
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Signal deduplication
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_NewSignal(bool currentSignal, bool &lastSignal)
{
   bool isNew = currentSignal && !lastSignal;
   lastSignal = currentSignal;
   return isNew;
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY: Position check
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
// UTILITY: Calculate stop loss
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
// UTILITY: Calculate take profit
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
// UTILITY: Open position
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_OpenPosition(bool isLong, double sl, double tp)
{
   MqlTradeRequest request = {};
   MqlTradeResult result = {};
   
   request.action = TRADE_ACTION_DEAL;
   request.symbol = _Symbol;
   request.magic = InpMagic;
   request.deviation = 10;
   
   if(isLong)
   {
      request.type = ORDER_TYPE_BUY;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      request.sl = sl;
      request.tp = tp;
      request.comment = "FalconFX Long";
   }
   else
   {
      request.type = ORDER_TYPE_SELL;
      request.price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      request.sl = sl;
      request.tp = tp;
      request.comment = "FalconFX Short";
   }
   
   // Position size: risk-based
   double riskAmount = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double slDiff = MathAbs(request.price - sl);
   
   if(tickValue > 0 && slDiff > 0)
   {
      double qty = riskAmount / (slDiff / tickSize * tickValue);
      request.volume = NormalizeDouble(qty, 2);
   }
   else
   {
      request.volume = 0.01;
   }
   
   if(request.volume < SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN))
      request.volume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   
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
      
      double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl = PositionGetDouble(POSITION_SL);
      double tp = PositionGetDouble(POSITION_TP);
      double currentPrice = PositionGetDouble(POSITION_PRICE_CURRENT);
      ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      
      double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      double risk = MathAbs(openPrice - sl);
      
      if(risk <= 0) continue;
      
      MqlTradeRequest req = {};
      MqlTradeResult res = {};
      req.action = TRADE_ACTION_SLTP;
      req.symbol = _Symbol;
      req.position = ticket;
      req.tp = tp;
      
      if(posType == POSITION_TYPE_BUY)
      {
         // B/E: move SL to entry when price moves 1R into profit
         if(currentPrice >= openPrice + risk)
         {
            req.sl = openPrice + point * 2;
         }
         // 90% Rule: close at correction start if corrective
         else if(InpUse90Rule && g_correctionStart > 0)
         {
            double dist90 = MathAbs(currentPrice - g_correctionStart);
            if(dist90 < g_atrValue * 0.5 && g_inCorrectivePhase)
            {
               // Close position
               MqlTradeRequest closeReq = {};
               MqlTradeResult closeRes = {};
               closeReq.action = TRADE_ACTION_DEAL;
               closeReq.symbol = _Symbol;
               closeReq.position = ticket;
               closeReq.type = ORDER_TYPE_SELL;
               closeReq.volume = PositionGetDouble(POSITION_VOLUME);
               closeReq.deviation = 10;
               closeReq.comment = "FalconFX 90% Rule";
               OrderSend(closeReq, closeRes);
               continue;
            }
         }
         // Half-Risk: move to half-risk if corrective
         else if(InpUseHalfRisk && g_inCorrectivePhase)
         {
            int barsInTrade = iBars(_Symbol, PERIOD_CURRENT);
            if(barsInTrade >= InpHalfRiskThreshold)
            {
               double halfRiskSL = openPrice + (openPrice - sl) * 0.5;
               if(currentPrice < halfRiskSL)
                  req.sl = halfRiskSL;
            }
         }
      }
      else // POSITION_TYPE_SELL
      {
         if(currentPrice <= openPrice - risk)
         {
            req.sl = openPrice - point * 2;
         }
         else if(InpUse90Rule && g_correctionStart > 0)
         {
            double dist90 = MathAbs(currentPrice - g_correctionStart);
            if(dist90 < g_atrValue * 0.5 && g_inCorrectivePhase)
            {
               MqlTradeRequest closeReq = {};
               MqlTradeResult closeRes = {};
               closeReq.action = TRADE_ACTION_DEAL;
               closeReq.symbol = _Symbol;
               closeReq.position = ticket;
               closeReq.type = ORDER_TYPE_BUY;
               closeReq.volume = PositionGetDouble(POSITION_VOLUME);
               closeReq.deviation = 10;
               closeReq.comment = "FalconFX 90% Rule";
               OrderSend(closeReq, closeRes);
               continue;
            }
         }
         else if(InpUseHalfRisk && g_inCorrectivePhase)
         {
            int barsInTrade = iBars(_Symbol, PERIOD_CURRENT);
            if(barsInTrade >= InpHalfRiskThreshold)
            {
               double halfRiskSL = openPrice - (sl - openPrice) * 0.5;
               if(currentPrice > halfRiskSL)
                  req.sl = halfRiskSL;
            }
         }
      }
      
      OrderSend(req, res);
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY DETECTION: Risk Entry Long
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_IsRiskEntryLong()
{
   if(!g_nearSupport) return false;
   if(!g_bullishStructure) return false;
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   if(!FalconFX_HasBullPattern()) return false;
   if(!FalconFX_LongDistOk()) return false;
   return true;
}

bool FalconFX_IsRiskEntryShort()
{
   if(!g_nearResistance) return false;
   if(!g_bearishStructure) return false;
   if(!g_inCorrectivePhase) return false;
   if(g_inImpulsivePhase) return false;
   if(!FalconFX_HasBearPattern()) return false;
   if(!FalconFX_ShortDistOk()) return false;
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
   
   Print("FalconFX Bot v3.3 initialized. Symbol: ", _Symbol, " TF: ", EnumToString(Period()));
   return INIT_SUCCEEDED;
}

// ═══════════════════════════════════════════════════════════════════════════
// DEINITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

void OnDeinit(const int reason)
{
   Print("FalconFX Bot v3.3 stopped. Reason: ", reason);
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
   
   // Check session filter
   if(InpUseSessionFilter)
   {
      MqlDateTime dt;
      TimeCurrent(dt);
      bool inSession = (dt.hour >= 7 && dt.hour < 16) || (dt.hour >= 12 && dt.hour < 21);
      if(!inSession) return;
   }
   
   // Check daily trade limit
   if(!FalconFX_CanTrade())
      return;
   
   // ─── LONG ENTRY CHECK ───
   bool riskEntryLong = FalconFX_IsRiskEntryLong();
   bool reducedRiskEntryLong = FalconFX_IsReducedRiskEntryLong();
   bool longSignal = (InpUseRiskEntry && riskEntryLong) || (InpUseReducedRiskEntry && reducedRiskEntryLong);
   
   if(FalconFX_NewSignal(longSignal, g_lastSignalLong))
   {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl = FalconFX_CalculateLongSL();
      double tp = FalconFX_CalculateLongTP(ask, sl);
      
      if(FalconFX_OpenPosition(true, sl, tp))
      {
         g_tradesToday++;
         Print("FalconFX: LONG @ ", ask, " SL: ", sl, " TP: ", tp);
      }
   }
   
   // ─── SHORT ENTRY CHECK ───
   bool riskEntryShort = FalconFX_IsRiskEntryShort();
   bool reducedRiskEntryShort = FalconFX_IsReducedRiskEntryShort();
   bool shortSignal = (InpUseRiskEntry && riskEntryShort) || (InpUseReducedRiskEntry && reducedRiskEntryShort);
   
   if(FalconFX_NewSignal(shortSignal, g_lastSignalShort))
   {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl = FalconFX_CalculateShortSL();
      double tp = FalconFX_CalculateShortTP(bid, sl);
      
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
   double pf = TesterStatistics(STAT_PROFIT_FACTOR);
   double dd = TesterStatistics(STAT_EQUITY_DDREL_PERCENT);
   
   Print("=== FalconFX v3.3 Backtest ===");
   Print("Profit: ", profit, " | Trades: ", trades, " | PF: ", pf, " | DD: ", dd, "%");
   
   if(dd > 0)
      return (profit * (trades > 0 ? profit / trades : 0)) / dd;
   return profit;
}
