<!-- uncomment for jsp file -->
<!--
<%@ page language="java" contentType="text/html; charset=utf-8"
	pageEncoding="utf-8" errorPage="/error.jsp"%>

<jsp:useBean id="transactionDetails" scope="request" type="com.creditguard.common.transactions.TransactionDetails" />
<%@ include file="/merchantPages/WebSources/includes/main.jsp" %>
-->

<%
String langdir="ltr";
String absvertpos="right: 0";
if(lang.equals("HE")){
    langdir="rtl";
    absvertpos="left: 0";
}
%>

{% extends "wb_base_mobile.html" %}
{% load i18n %}

{% block extrastyle %}
    {{ block.super }}
    <style type="text/css">
        body {
            direction: <%=langdir%>;
        }

        #wb_lock {
            width: 33px;
            height: 52px;
            background: url("/static/images/wb_site/lock.png") left 0 no-repeat;
            display: inline-block;
            position: relative;
        }

        #wb_CVVhelp {
            width: 225px;
            height: 125px;
            display: block;
            background: url("/static/images/wb_site/cvv.png") left 0 no-repeat;
        }

        #qm {
            display: inline-block;
            height: 18px;
            width: 18px;
            position: relative;
            top: 3px;
            cursor: pointer;
            background: url("/static/images/wb_site/question_mark.png") left 0 no-repeat;
            <% if (langdir.equals("ltr")) { %>
                margin-left: 30px;
            <% } else { %>
                margin-right: 30px;
            <% } %>

        }

        #cvv {
            display: inline-block;
            width: 50%;
        }

        #payment-header {
            text-align: center;
            vertical-align: top;
            height: 40px;
            font-weight: bold;
            background: url("/static/images/wb_site/lock.png") 20px 0px no-repeat;
            padding-top: 8px;

        }

        label.ui-input-text, label.ui-select {
            margin-top: 10px;
        }

        #personalId {
            margin-bottom: 40px;
        }

    </style>

{% endblock %}

{% block extrahead %}
    {{ block.super }}
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="cache-control" content="no-cache">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="-1">
    <script src="merchantPages/WebSources/js/<%=lang%>.js"></script>
    <script src="merchantPages/WebSources/js/main.js"></script>
    <%
    String langdir="ltr";
    String absvertpos="right: 0";
    if(lang.equals("HE")){
        langdir="rtl";
        absvertpos="left: 0";
    }
    %>
{% endblock %}

{% block body %}
    <div id="credit_guard_page" data-role="page" data-theme="a">
        <div data-role="header">
            <h1>
                <% if (lang.equals("HE")) { %>
                    הצטרף לWAYbetter
                <% } else { %>
                    Join WAYbetter
                <% } %>
            </h1>
            <table class="registration-progress-bar">
                <tr>
                    <td class="done">1.
                        <% if (lang.equals("HE")) { %>
                            פרטים
                        <% } else { %>
                            Details
                        <% } %>
                    </td>
                    <td class="done">1.
                        <% if (lang.equals("HE")) { %>
                            טלפון
                        <% } else { %>
                            Phone
                        <% } %>
                    </td>
                    <td class="current">1.
                        <% if (lang.equals("HE")) { %>
                            פרטי חיוב
                        <% } else { %>
                            Billing
                        <% } %>
                    </td>
                </tr>
            </table>
        </div>
        <div data-role="content">
            <div id="payment-header">
                <% if (lang.equals("HE")) { %>
                    דף תשלום מאובטח SSL
                <% } else { %>
                    SSL Secured Payment
                <% } %>

            </div>
            <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard">
                <input type="hidden" name="txId" value="<%=mpiTxnId%>"/>
                <input type="hidden" name="lang" value="EN"/>
                <input type="hidden" name="track2" value="" autocomplete="off"/>
                <input type="hidden" name="last4d" value="" autocomplete="off"/>
                <input type="hidden" name="cavv" value="" autocomplete="off"/>
                <input type="hidden" name="eci" value="" autocomplete="off"/>
                <input type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>

                <label for="cardNumber"><%=CCNumber%></label>
                <input type="text" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/>

                <label for="expYear"><%=CCExp%></label>

                <div class="ui-grid-a">
                    <div class="ui-block-a">
                        <select id="expYear" name="expYear">
                            <%=expYear%>
                        </select>
                    </div>
                    <div class="ui-block-b">
                        <select id="expMonth" name="expMonth">
                            <option value="01">01</option>
                            <option value="02">02</option>
                            <option value="03">03</option>
                            <option value="04">04</option>
                            <option value="05">05</option>
                            <option value="06">06</option>
                            <option value="07">07</option>
                            <option value="08">08</option>
                            <option value="09">09</option>
                            <option value="10">10</option>
                            <option value="11">11</option>
                            <option value="12">12</option>
                        </select>
                    </div>
                </div>

                <label for="cvv">CVV</label>
                <input type="text" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                <a href="#cvv_dialog" data-rel="dialog">
                    <span id="qm" src="merchantPages/WebSources/images/qm.png"></span>
                </a>


                <label for="personalId"><%=CCPId%></label>
                <input type="text" id="personalId" name="personalId" maxlength="9" autocomplete="off"/>

                <input type="submit" id="submitBtn" data-theme="d" value="<%=formSend%>"/>
                <div class="hidden">
                    {# need this to avoid js errors from CreditGuard's scripts #}
                    <input id="resetBtn" type="reset" value="<%=formReset%>"/>
                </div>
            </form>
        </div>
    </div>

    <div id="cvv_dialog" data-role="page">
        <div data-role="header">
            <h1>CVV</h1>
        </div>
        <div data-role="content">
            <span id="wb_CVVhelp"></span>
        </div>
    </div>
{% endblock body %}
