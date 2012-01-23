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

{% extends "wb_base_site.html" %}
{% load i18n %}
{% block htmlclass %}{{ block.super }} <%=langdir%>{% endblock %}
{% block bodyclass %}{{ block.super }} <%=langdir%>{% endblock %}
{% block extrahead %}
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
    <meta http-equiv="cache-control" content="no-cache">
    <meta http-equiv="pragma" content="no-cache">
    <meta http-equiv="expires" content="-1">
    <script src="merchantPages/WebSources/js/<%=lang%>.js"></script>
    <script src="merchantPages/WebSources/js/main.js"></script>

{% endblock %}
{% block extrastyle %}
    {{ block.super }}
    <style type="text/css">
        *{
            direction: <%=langdir%>;
        }
    </style>
{% endblock %}

{% block header_links %}{% endblock %}
{% block top_left %}
    <% if (lang.equals("HE")) { %>
    <% } else { %>
    Secured Payment Page
    <div id="wb_lock"></div>
    <% } %>
{% endblock %}

{% block top_right %}
    <% if (lang.equals("HE")) { %>
    <div id="wb_lock"></div>
    דף תשלום מאובטח
    <% } else { %>
    <% } %>
{% endblock %}

{% block content %}
    <table id="progress">
        <tr>
            <td class="step">
                <% if (lang.equals("HE")) { %>
                1. פרטי חשבון
                <% } else { %>
                1. Account Information
                <% } %>
            </td>
            <td class="step">
                <% if (lang.equals("HE")) { %>
                2. אימות טלפון
                <% } else { %>
                2. Phone Verification
                <% } %>
            </td>
            <td class="step current">
                <% if (lang.equals("HE")) { %>
                3. פרטי חיוב
                <% } else { %>
                3. Billing Information
                <% } %>
            </td>
        </tr>
    </table>

    <div class="spacer top"></div>

    <form id="creditForm" onsubmit="return formValidator(0);" method="POST" action="ProcessCreditCard">

        <table id="billing_step">
            <tr class="header-row">
                <td colspan="2">
                    <div class="step-header">
                        <% if (lang.equals("HE")) { %>
                        פרטי חיוב
                        <% } else { %>
                        Billing Information
                        <% } %>
                    </div>
                </td>
            </tr>
            <tr>
                <td class="form cntr">
                    <input type="hidden" name="txId" value="<%=mpiTxnId%>"/>
                    <input type="hidden" name="lang" value="EN"/>
                    <input type="hidden" name="track2" value="" autocomplete="off"/>
                    <input type="hidden" name="last4d" value="" autocomplete="off"/>
                    <input type="hidden" name="cavv" value="" autocomplete="off"/>
                    <input type="hidden" name="eci" value="" autocomplete="off"/>
                    <input type="hidden" name="transactionCode" value="Phone" autocomplete="off"/>
                    <table class="data_tbl">
                        <tr>
                            <td class="td_style_fieldName"><%=CCNumber%></td>
                            <td><input type="text" id="cardNumber" name="cardNumber" maxlength="19" autocomplete="off"/>
                            </td>
                            <td class="td_style_fieldName"></td>
                        </tr>
                        <tr>
                            <td class="td_style_fieldName"><%=CCExp%></td>
                            <td>
                                <select id="expYear" name="expYear">
                                    <%=expYear%>
                                </select>
                                -
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
                            </td>
                            <td class="td_style_fieldName"></td>
                        </tr>
                        <tr>
                            <td class="td_style_fieldName">CVV</td>
                            <td><input type="text" name="cvv" id="cvv" maxlength="4" autocomplete="off"/>
                                <span id="qm" src="merchantPages/WebSources/images/qm.png"></span>

                                <span id="wb_CVVhelp"></span>
                            </td>
                            <td class="td_style_fieldName"></td>
                        </tr>
                        <tr>
                            <td class="td_style_fieldName"><%=CCPId%></td>
                            <td><input type="text" id="personalId" name="personalId" maxlength="9" autocomplete="off"/>
                            </td>
                            <td class="td_style_fieldName"></td>
                        </tr>
                    </table>
                </td>
                <td class="img cntr">
                    <div id="invoice-img"></div>
                </td>
            </tr>

            <tr>
                <td colspan="2">
                    <div class="spacer bottom"></div>
                </td>
            </tr>
            <tr id="submit_row">
                <td>
                    <span class="bold">
                        <% if (lang.equals("HE")) { %>
                        אתה בטוח:
                        <% } else { %>
                        You are safe:
                        <% } %>
                    </span>
                    <br>
                    <% if (lang.equals("HE")) { %>
                    WAYbetter אינה שומרת או מחזיקה בפרטי האשראי שלך. פרטי האשראי נשמרים בצורה מאובטחת בחברת Credit Guard.
                    <% } else { %>
                    WAYbetter does not store nor hold any of your details. You are professionally secured with Credit Guard
                    <% } %>
                </td>
                <td id="button_container">
                    <input type="submit" class="wb_button" id="submitBtn" value="<%=formSend%>"/>
                    <input id="resetBtn" type="reset" style="display: none" value="<%=formReset%>"/>
                </td>
            </tr>
        </table>
    </form>

{% endblock %}

{% block post_content %}
    <div id="logos"></div>
{% endblock %}

{% block footer %}
{% endblock %}

{% block scripts %}{% endblock %}
{% block doc_ready %}
    <script type="text/javascript">
        $(function() {
            $("#wb_logo").click(function() {
                window.location.href = "http://www.waybetter.com";
            });
            $("#lang_dropdown").hide();
            $("#qm").bind("mouseover mouseout", function() {
                var $help = $("#wb_CVVhelp");
                if ($help.is(":visible")) {
                    $help.hide();
                }
                else {
                    $help.show();
                }
            });
        })
    </script>
{% endblock %}