// ============================================================================
// FalconFX_Management.mqh — Trade Management for MT5
// FalconFX Strategy Handbook Implementation
//
// Implements:
// - Break-Even Method (P16-20)
// - Half-Risk Method (P21)
// - 90% Rule Profit Locking (P22)
// - Scaling In (P24-27)
// - Position Sizing (1% risk cap)
// ═══════════════════════════════════════════════════════════════════════════

#ifndef FALCONFX_MANAGEMENT_MQH
#define FALCONFX_MANAGEMENT_MQH

#include <Trade\Trade.mqh>
#include <PositionInfo.mqh>
#include <OrderInfo.mqh>

// ═══════════════════════════════════════════════════════════════════════════
// INPUT PARAMETERS
// ═══════════════════════════════════════════════════════════════════════════

input group "═══ TRADE MANAGEMENT ═══"
input double InpRiskPercent      = 1.0;   // Risk Per Trade %
input int    InpMaxTradesPerDay  = 2;     // Max Trades Per Day
input bool   InpUseHalfRiskMethod = true;  // Enable Half-Risk Method
input int    InpHalfRiskHours    = 4;     // Hours before Half-Risk trigger
input double InpTPRatio          = 3.0;   // Take Profit R:R Ratio
input double InpBETrigger        = 1.5;   // B/E trigger (x R profit before moving SL)

input group "═══ SCALING IN (Advanced) ═══"
input bool   InpEnableScalingIn  = false;  // Enable Scaling In
input int    InpMaxScaleIns      = 2;     // Max Scale-Ins per Trade
input double InpScaleInRisk      = 1.0;   // Scale-In Risk %

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL STATE
// ═══════════════════════════════════════════════════════════════════════════

int          g_tradesToday      = 0;
int          g_lastTradeDay      = 0;
int          g_scaleInCount      = 0;
double       g_entryPrice        = 0.0;
double       g_entrySL           = 0.0;
double       g_entryTP           = 0.0;
bool         g_positionOpen      = false;
bool         g_isLong            = false;
datetime     g_positionOpenTime  = 0;
CTrade       g_trade;
CPositionInfo g_position;

// ═══════════════════════════════════════════════════════════════════════════
// MAGIC NUMBER
// ═══════════════════════════════════════════════════════════════════════════

// Magic number MUST match InpMagic in FalconFX.mq5 (498817)
// This is how the EA identifies its own positions vs other EAs.
#define FALCONFX_MAGIC 498817

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_MgmtInit()
{
   g_trade.SetExpertMagicNumber(FALCONFX_MAGIC);
   g_trade.SetDeviationInPoints(10);
   g_trade.SetTypeFilling(ORDER_FILLING_IOC);
   
   Print("FalconFX Management initialized. Magic: ", FALCONFX_MAGIC);
   return true;
}

// ═══════════════════════════════════════════════════════════════════════════
// DAILY TRADE COUNTER RESET
// "Max 2 trades per day — prevents FOMO, revenge trading, chasing tail"
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_ResetDailyCounter()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   
   if(dt.day != g_lastTradeDay)
   {
      g_tradesToday = 0;
      g_lastTradeDay = dt.day;
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// CAN WE TRADE?
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_CanTrade()
{
   FalconFX_ResetDailyCounter();
   return (g_tradesToday < InpMaxTradesPerDay);
}

// ═══════════════════════════════════════════════════════════════════════════
// POSITION SIZING — 1% risk cap (Handbook P4-5)
// "Cap your risk to 1% per trade"
// ═══════════════════════════════════════════════════════════════════════════

double FalconFX_CalculateLotSize(double slDistance)
{
   if(slDistance <= 0) return 0;
   
   double accountBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskAmount     = accountBalance * (InpRiskPercent / 100.0);
   
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   
   if(tickValue <= 0 || tickSize <= 0) return 0;
   
   double lotSize = riskAmount / (slDistance / tickSize * tickValue);
   
   // Normalize lot size
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   
   lotSize = MathFloor(lotSize / lotStep) * lotStep;
   lotSize = MathMax(minLot, MathMin(maxLot, lotSize));
   
   return lotSize;
}

// ═══════════════════════════════════════════════════════════════════════════
// OPEN POSITION
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_OpenPosition(bool isLong, double sl, double tp)
{
   if(!FalconFX_CanTrade())
   {
      Print("FalconFX: Max trades reached for today. Skipping.");
      return false;
   }
   
   double lotSize = FalconFX_CalculateLotSize(MathAbs(sl - SymbolInfoDouble(_Symbol, SYMBOL_ASK)));
   if(lotSize <= 0)
   {
      Print("FalconFX: Invalid lot size. SL distance too small.");
      return false;
   }
   
   double price;
   bool result;
   
   if(isLong)
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      result = g_trade.Buy(lotSize, _Symbol, price, sl, tp, "FalconFX Long");
   }
   else
   {
      price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      result = g_trade.Sell(lotSize, _Symbol, price, sl, tp, "FalconFX Short");
   }
   
   if(result)
   {
      g_entryPrice       = price;
      g_entrySL          = sl;
      g_entryTP          = tp;
      g_positionOpen     = true;
      g_isLong           = isLong;
      g_positionOpenTime = TimeCurrent();
      g_scaleInCount     = 0;
      g_tradesToday++;
      
      Print("FalconFX: Position opened. ", isLong ? "LONG" : "SHORT", 
            " @ ", price, " SL: ", sl, " TP: ", tp, " Lot: ", lotSize);
   }
   else
   {
      Print("FalconFX: Failed to open position. Error: ", GetLastError());
   }
   
   return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// BREAK-EVEN METHOD (Handbook P16-20)
// "Move stop loss to entry point when price has impulsed away"
// "Normal: when price moves 1% into profit or reaches recent high/low"
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_ApplyBreakEven()
{
   if(!g_positionOpen) return;
   
   double currentPrice = g_isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double riskDistance = MathAbs(g_entryPrice - g_entrySL);
   
   if(riskDistance <= 0) return;
   
   double moveInProfit = g_isLong ? (currentPrice - g_entryPrice) : (g_entryPrice - currentPrice);
   
   // Trigger: price moves BETrigger R-multiples into profit OR at least 1R
   double triggerDistance = riskDistance * InpBETrigger;
   
   if(moveInProfit >= triggerDistance)
   {
      // Move SL to entry + small buffer
      double buffer = SymbolInfoDouble(_Symbol, SYMBOL_POINT) * 2;
      double newSL = g_isLong ? g_entryPrice + buffer : g_entryPrice - buffer;
      
      // Find and modify the open POSITION (not pending order)
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0) continue;
         if(PositionGetInteger(POSITION_MAGIC) != FALCONFX_MAGIC) continue;
         
         double currentSL = PositionGetDouble(POSITION_SL);
         double currentTP = PositionGetDouble(POSITION_TP);
         
         // Only move SL in our favor
         if(g_isLong && newSL > currentSL)
         {
            if(g_trade.PositionModify(ticket, newSL, currentTP))
               Print("FalconFX: B/E applied. New SL: ", newSL);
         }
         else if(!g_isLong && newSL < currentSL)
         {
            if(g_trade.PositionModify(ticket, newSL, currentTP))
               Print("FalconFX: B/E applied. New SL: ", newSL);
         }
         break;
      }
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// HALF-RISK METHOD (Handbook P21)
// "When price does NOT impulse away from entry (corrective behavior)
// move stop to -0.5% risk. Market is telling us structure is evolving"
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_ApplyHalfRisk()
{
   if(!g_positionOpen || !InpUseHalfRiskMethod) return;
   
   datetime currentTime = TimeCurrent();
   int barsInTrade = (currentTime - g_positionOpenTime) / PeriodSeconds();
   int hoursInTrade = barsInTrade / 3600;
   
   if(hoursInTrade < InpHalfRiskHours) return;
   
   double currentPrice = g_isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double riskDistance = MathAbs(g_entryPrice - g_entrySL);
   
   if(riskDistance <= 0) return;
   
   double moveInProfit = g_isLong ? (currentPrice - g_entryPrice) : (g_entryPrice - currentPrice);
   
   // If price hasn't moved at least 50% into profit, move to half-risk
   if(moveInProfit < riskDistance * 0.5)
   {
      double halfRiskSL;
      
      if(g_isLong)
         halfRiskSL = g_entryPrice - (riskDistance * 0.5);  // -0.5R
      else
         halfRiskSL = g_entryPrice + (riskDistance * 0.5);
      
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0) continue;
         if(PositionGetInteger(POSITION_MAGIC) != FALCONFX_MAGIC) continue;
         
         double currentSL = PositionGetDouble(POSITION_SL);
         double currentTP = PositionGetDouble(POSITION_TP);
         
         if(g_isLong && halfRiskSL > currentSL)
         {
            if(g_trade.PositionModify(ticket, halfRiskSL, currentTP))
               Print("FalconFX: Half-Risk applied. New SL: ", halfRiskSL);
         }
         else if(!g_isLong && halfRiskSL < currentSL)
         {
            if(g_trade.PositionModify(ticket, halfRiskSL, currentTP))
               Print("FalconFX: Half-Risk applied. New SL: ", halfRiskSL);
         }
         break;
      }
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// 90% RULE PROFIT LOCKING (Handbook P22)
// "Place a ray line at the correction start point. Watch nature as we approach.
// If reversal forms, take action. If not, allow trade to continue."
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_Apply90PercentRule()
{
   if(!g_positionOpen) return;
   
   double correctionStart = FalconFX_Get90PercentLevel();
   if(correctionStart == 0.0) return;
   
   double currentPrice = g_isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double atr = FalconFX_GetATR(0);
   
   double distTo90 = MathAbs(currentPrice - correctionStart);
   
   // If approaching 90% level and showing corrective behavior
   if(distTo90 < atr * 0.5 && g_inCorrectivePhase)
   {
      // Close POSITION using position ticket (not order ticket)
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         ulong ticket = PositionGetTicket(i);
         if(ticket == 0) continue;
         if(PositionGetInteger(POSITION_MAGIC) != FALCONFX_MAGIC) continue;
         
         if(g_trade.PositionClose(ticket))
            Print("FalconFX: 90% Rule - Position closed at correction start.");
         break;
      }
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// SCALING IN (Handbook P24-27)
// "Add a second position on the next continuation correction"
// "Cannot add until first position is at break-even"
// "Initial Position: BE | Scale-In: 1% risk | Overall: 1% risk"
// ═══════════════════════════════════════════════════════════════════════════

bool FalconFX_TryScaleIn()
{
   if(!InpEnableScalingIn) return false;
   if(!g_positionOpen) return false;
   if(g_scaleInCount >= InpMaxScaleIns) return false;
   
   // Check if position is at break-even
   double currentPrice = g_isLong ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double riskDistance = MathAbs(g_entryPrice - g_entrySL);
   double moveInProfit = g_isLong ? (currentPrice - g_entryPrice) : (g_entryPrice - currentPrice);
   
   if(moveInProfit < riskDistance) return false;  // Not at BE yet
   
   // Check for corrective phase (continuation pattern forming)
   if(!g_inCorrectivePhase) return false;
   
   // Wait for impulse to resume after correction
   static bool wasCorrective = false;
   bool impulseResumed = wasCorrective && g_inImpulsivePhase;
   wasCorrective = g_inCorrectivePhase;
   
   if(!impulseResumed) return false;
   
   // Scale in with reduced size
   double scaleInLot = FalconFX_CalculateLotSize(riskDistance) * 0.5;
   if(scaleInLot <= 0) return false;
   
   bool result;
   if(g_isLong)
      result = g_trade.Buy(scaleInLot, _Symbol, SymbolInfoDouble(_Symbol, SYMBOL_ASK), 
                            g_entrySL, g_entryTP, "FalconFX Scale-In Long");
   else
      result = g_trade.Sell(scaleInLot, _Symbol, SymbolInfoDouble(_Symbol, SYMBOL_BID), 
                             g_entrySL, g_entryTP, "FalconFX Scale-In Short");
   
   if(result)
   {
      g_scaleInCount++;
      Print("FalconFX: Scale-In #", g_scaleInCount, " executed.");
   }
   
   return result;
}

// ═══════════════════════════════════════════════════════════════════════════
// POSITION TRACKING
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_UpdatePositionState()
{
   // Check if we still have an open position
   bool found = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == FALCONFX_MAGIC)
      {
         found = true;
         break;
      }
   }
   
   if(!found && g_positionOpen)
   {
      // Position was closed (SL/TP hit)
      g_positionOpen = false;
      g_scaleInCount = 0;
      Print("FalconFX: Position closed.");
   }
}

// ═══════════════════════════════════════════════════════════════════════════
// MASTER MANAGEMENT CALL (called on every tick)
// ═══════════════════════════════════════════════════════════════════════════

void FalconFX_ManageOpenPositions()
{
   FalconFX_UpdatePositionState();
   
   if(!g_positionOpen) return;
   
   FalconFX_ApplyBreakEven();
   FalconFX_ApplyHalfRisk();
   FalconFX_Apply90PercentRule();
   FalconFX_TryScaleIn();
}

#endif // FALCONFX_MANAGEMENT_MQH
